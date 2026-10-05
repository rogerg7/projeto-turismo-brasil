"""
Dashboard — Turismo no Brasil (2015–2024)
Projeto G2 · Tema 18 · Análise e Visualização de Dados com Python

Fluxo: CSV -> tratamento (Pandas) -> persistência (SQLAlchemy + SQLite) -> dashboard (Streamlit + Plotly + Seaborn)
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
import streamlit as st
from sqlalchemy import create_engine

# ----------------------------------------------------------------------------
# Configurações gerais
# ----------------------------------------------------------------------------
PASTA_BASE = Path(__file__).parent
CAMINHO_CSV = PASTA_BASE / "dados" / "simulacao_turismo_brasil.csv"
CAMINHO_BANCO = PASTA_BASE / "database" / "turismo.db"

NOMES_MESES = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}
MESES_TEXTO = {
    "janeiro": 1, "jan": 1, "fevereiro": 2, "fev": 2, "marco": 3, "março": 3, "mar": 3,
    "abril": 4, "abr": 4, "maio": 5, "mai": 5, "junho": 6, "jun": 6,
    "julho": 7, "jul": 7, "agosto": 8, "ago": 8, "setembro": 9, "set": 9,
    "outubro": 10, "out": 10, "novembro": 11, "nov": 11, "dezembro": 12, "dez": 12,
}
ORDEM_TEMPORADA = ["Baixa", "Média", "Alta"]
TEMPORADA_TEXTO = {"baixa": "Baixa", "media": "Média", "média": "Média", "alta": "Alta"}

COLUNAS_OBRIGATORIAS = [
    "ano", "mes", "data", "regiao", "uf", "cidade", "turistas", "turistas_estrangeiros",
    "ocupacao_hoteleira", "gasto_medio", "faturamento_turismo", "eventos_realizados",
    "temperatura_media", "nivel_temporada",
]
COLUNAS_NUMERICAS = [
    "turistas", "turistas_estrangeiros", "ocupacao_hoteleira", "gasto_medio",
    "faturamento_turismo", "eventos_realizados", "temperatura_media",
]
ROTULOS = {
    "turistas": "Turistas",
    "turistas_estrangeiros": "Turistas estrangeiros",
    "ocupacao_hoteleira": "Ocupação hoteleira (%)",
    "gasto_medio": "Gasto médio (R$)",
    "faturamento_turismo": "Faturamento (R$)",
    "eventos_realizados": "Eventos realizados",
    "temperatura_media": "Temperatura média (°C)",
}

st.set_page_config(page_title="Turismo no Brasil", page_icon="🧭", layout="wide")


# ----------------------------------------------------------------------------
# Funções de formatação
# ----------------------------------------------------------------------------
def formatar_inteiro(valor):
    return f"{valor:,.0f}".replace(",", ".")


def abreviar(valor, prefixo=""):
    """Abrevia números grandes no padrão brasileiro (mil, mi, bi)."""
    for limite, sufixo in ((1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
        if abs(valor) >= limite:
            texto = f"{valor / limite:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return f"{prefixo}{texto}{sufixo}"
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{prefixo}{texto}"


def formatar_decimal(valor, casas=1):
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ----------------------------------------------------------------------------
# Leitura, tratamento e persistência
# ----------------------------------------------------------------------------
def ler_csv_bruto(caminho):
    """Lê o CSV detectando o separador e tentando duas codificações."""
    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(caminho, sep=None, engine="python", encoding=codificacao)
        except UnicodeDecodeError:
            continue
    raise ValueError("Não foi possível ler o CSV. Verifique a codificação do arquivo.")


def tratar_dados(bruto):
    """Limpeza, padronização e engenharia de atributos."""
    base = bruto.copy()
    base.columns = [coluna.strip().lower() for coluna in base.columns]

    faltando = [coluna for coluna in COLUNAS_OBRIGATORIAS if coluna not in base.columns]
    if faltando:
        raise ValueError(f"Colunas ausentes no CSV: {faltando}")

    # Colunas numéricas (aceita vírgula decimal)
    for coluna in COLUNAS_NUMERICAS + ["ano"]:
        if base[coluna].dtype == object:
            base[coluna] = base[coluna].astype(str).str.replace(",", ".", regex=False)
        base[coluna] = pd.to_numeric(base[coluna], errors="coerce")

    # Colunas de texto
    for coluna in ("regiao", "uf", "cidade", "nivel_temporada"):
        base[coluna] = base[coluna].astype(str).str.strip()
    base["uf"] = base["uf"].str.upper()
    base["nivel_temporada"] = (
        base["nivel_temporada"].str.lower().map(TEMPORADA_TEXTO).fillna(base["nivel_temporada"])
    )

    # Mês pode vir como número ou como nome
    if base["mes"].dtype == object:
        base["mes"] = base["mes"].astype(str).str.strip().str.lower().map(MESES_TEXTO)
    base["mes"] = pd.to_numeric(base["mes"], errors="coerce")

    # Duplicatas e linhas sem informação essencial
    base = base.drop_duplicates()
    essenciais = ["ano", "mes", "cidade", "turistas", "faturamento_turismo"]
    base = base.dropna(subset=essenciais)
    base["ano"] = base["ano"].astype(int)
    base["mes"] = base["mes"].astype(int)

    # Nulos nas demais numéricas: mediana da própria cidade (depois, mediana geral)
    for coluna in COLUNAS_NUMERICAS:
        base[coluna] = base[coluna].fillna(base.groupby("cidade")[coluna].transform("median"))
        base[coluna] = base[coluna].fillna(base[coluna].median())

    # Ocupação em escala 0–100
    if base["ocupacao_hoteleira"].max() <= 1.5:
        base["ocupacao_hoteleira"] = base["ocupacao_hoteleira"] * 100

    # Data padronizada: primeiro dia de cada mês
    base["data"] = pd.to_datetime(dict(year=base["ano"], month=base["mes"], day=1))

    # Engenharia de atributos
    base["nome_mes"] = base["mes"].map(NOMES_MESES)
    base["trimestre"] = "T" + ((base["mes"] - 1) // 3 + 1).astype(str)
    base["pct_estrangeiros"] = base["turistas_estrangeiros"] / base["turistas"] * 100
    base["faturamento_por_turista"] = base["faturamento_turismo"] / base["turistas"]

    return base.sort_values(["data", "regiao", "cidade"]).reset_index(drop=True)


@st.cache_data(show_spinner="Carregando dados...")
def carregar_dados():
    """Persiste a base tratada em SQLite (SQLAlchemy) e lê de volta do banco."""
    motor = create_engine(f"sqlite:///{CAMINHO_BANCO}")
    CAMINHO_BANCO.parent.mkdir(exist_ok=True)

    banco_desatualizado = (
        not CAMINHO_BANCO.exists()
        or CAMINHO_BANCO.stat().st_mtime < CAMINHO_CSV.stat().st_mtime
    )
    if banco_desatualizado:
        tratar_dados(ler_csv_bruto(CAMINHO_CSV)).to_sql(
            "turismo", motor, if_exists="replace", index=False
        )

    base = pd.read_sql("SELECT * FROM turismo", motor, parse_dates=["data"])
    base["nivel_temporada"] = pd.Categorical(
        base["nivel_temporada"], categories=ORDEM_TEMPORADA, ordered=True
    )
    return base


# ----------------------------------------------------------------------------
# Carregamento
# ----------------------------------------------------------------------------
if not CAMINHO_CSV.exists():
    st.error(
        "Arquivo `dados/simulacao_turismo_brasil.csv` não encontrado. "
        "Coloque a base do professor nessa pasta e recarregue a página."
    )
    st.stop()

try:
    base = carregar_dados()
except ValueError as erro:
    st.error(str(erro))
    st.stop()

# ----------------------------------------------------------------------------
# Cabeçalho
# ----------------------------------------------------------------------------
st.title("🧭 Turismo no Brasil (2015–2024)")
st.markdown(
    """
**Problema.** O turismo movimenta empregos, serviços e infraestrutura, mas o fluxo de visitantes
muda conforme a época do ano, os eventos, o clima e a região. Este painel investiga **quais destinos
mais recebem turistas, quando ocorre a alta temporada, quais regiões movimentam mais recursos e como
o setor evoluiu ao longo do tempo**.

*Base utilizada: dataset simulado `simulacao_turismo_brasil.csv`, fornecido para fins educacionais.*
"""
)

# ----------------------------------------------------------------------------
# Filtros (barra lateral)
# ----------------------------------------------------------------------------
st.sidebar.header("Filtros")

anos = sorted(base["ano"].unique())
anos_sel = st.sidebar.multiselect("Ano", anos, default=anos)

meses_sel = st.sidebar.multiselect(
    "Mês", list(range(1, 13)), default=list(range(1, 13)), format_func=lambda m: NOMES_MESES[m]
)

regioes = sorted(base["regiao"].unique())
regioes_sel = st.sidebar.multiselect("Região", regioes, default=regioes)

ufs = sorted(base[base["regiao"].isin(regioes_sel)]["uf"].unique())
ufs_sel = st.sidebar.multiselect("Estado (UF)", ufs, default=ufs)

cidades = sorted(
    base[base["regiao"].isin(regioes_sel) & base["uf"].isin(ufs_sel)]["cidade"].unique()
)
cidades_sel = st.sidebar.multiselect("Cidade", cidades, default=cidades)

temporadas_sel = st.sidebar.multiselect("Nível de temporada", ORDEM_TEMPORADA, default=ORDEM_TEMPORADA)

dados = base[
    base["ano"].isin(anos_sel)
    & base["mes"].isin(meses_sel)
    & base["regiao"].isin(regioes_sel)
    & base["uf"].isin(ufs_sel)
    & base["cidade"].isin(cidades_sel)
    & base["nivel_temporada"].isin(temporadas_sel)
]

st.sidebar.caption(f"{formatar_inteiro(len(dados))} registros no filtro atual")

if dados.empty:
    st.warning("Nenhum registro encontrado com os filtros atuais. Amplie a seleção na barra lateral.")
    st.stop()

# ----------------------------------------------------------------------------
# KPIs
# ----------------------------------------------------------------------------
total_turistas = dados["turistas"].sum()
receita_total = dados["faturamento_turismo"].sum()
ocupacao_media = dados["ocupacao_hoteleira"].mean()
gasto_medio = np.average(dados["gasto_medio"], weights=dados["turistas"])

turistas_por_cidade = dados.groupby("cidade")["turistas"].sum().sort_values(ascending=False)
turistas_por_regiao = dados.groupby("regiao")["turistas"].sum().sort_values(ascending=False)
cidade_top = turistas_por_cidade.index[0]
regiao_top = turistas_por_regiao.index[0]

media_mensal = dados.groupby(["mes", "nome_mes"], as_index=False)["turistas"].mean()
amplitude_sazonal = (
    (media_mensal["turistas"].max() - media_mensal["turistas"].min()) / media_mensal["turistas"].mean() * 100
)
correlacao_receita = dados["turistas"].corr(dados["faturamento_turismo"])
correlacao_clima = dados["temperatura_media"].corr(dados["turistas"])


def classificar(r):
    """Descreve a força e o sinal de uma correlação de Pearson."""
    if np.isnan(r):
        return "indefinida"
    if abs(r) < 0.2:
        return "praticamente nula"
    intensidade = "forte" if abs(r) >= 0.7 else "moderada" if abs(r) >= 0.4 else "fraca"
    return f"{intensidade} {'positiva' if r > 0 else 'negativa'}"


col1, col2, col3 = st.columns(3)
col1.metric("Total de turistas", abreviar(total_turistas))
col2.metric("Receita total do turismo", abreviar(receita_total, "R$ "))
col3.metric("Cidade mais visitada", cidade_top, f"{abreviar(turistas_por_cidade.iloc[0])} turistas", delta_color="off")

col4, col5, col6 = st.columns(3)
col4.metric("Ocupação hoteleira média", f"{formatar_decimal(ocupacao_media)}%")
col5.metric("Gasto médio por turista", abreviar(gasto_medio, "R$ "))
col6.metric("Região mais movimentada", regiao_top, f"{abreviar(turistas_por_regiao.iloc[0])} turistas", delta_color="off")

st.divider()

# ----------------------------------------------------------------------------
# Seções
# ----------------------------------------------------------------------------
abas = st.tabs([
    "📈 Evolução temporal",
    "🗺️ Regiões",
    "🏙️ Destinos",
    "📅 Sazonalidade",
    "💰 Economia e clima",
    "🏨 Ocupação hoteleira",
    "🔎 Tabela dinâmica",
    "✅ Conclusão executiva",
])

# --- Evolução temporal -------------------------------------------------------
with abas[0]:
    st.subheader("Evolução do turismo ao longo do tempo")

    serie = dados.groupby("data", as_index=False)["turistas"].sum()
    serie["media_movel_3m"] = serie["turistas"].rolling(3, min_periods=1).mean()

    figura = go.Figure()
    figura.add_trace(go.Scatter(x=serie["data"], y=serie["turistas"], mode="lines",
                                name="Turistas (mensal)", line=dict(width=1.5)))
    figura.add_trace(go.Scatter(x=serie["data"], y=serie["media_movel_3m"], mode="lines",
                                name="Média móvel (3 meses)", line=dict(width=3, dash="dot")))
    figura.update_layout(template="plotly_white", yaxis_title="Turistas", xaxis_title=None,
                         legend=dict(orientation="h", y=1.1))
    st.plotly_chart(figura, width="stretch")

    anual = dados.groupby("ano", as_index=False).agg(
        turistas=("turistas", "sum"), faturamento=("faturamento_turismo", "sum")
    )
    anual["crescimento_pct"] = anual["turistas"].pct_change() * 100

    esquerda, direita = st.columns(2)
    with esquerda:
        figura = px.bar(anual, x="ano", y="turistas", template="plotly_white",
                        title="Turistas por ano", labels={"turistas": "Turistas", "ano": "Ano"})
        st.plotly_chart(figura, width="stretch")
    with direita:
        crescimento = anual.dropna(subset=["crescimento_pct"])
        if crescimento.empty:
            st.info("Selecione pelo menos dois anos consecutivos para ver o crescimento anual.")
        else:
            figura = px.bar(crescimento, x="ano", y="crescimento_pct", template="plotly_white",
                            title="Crescimento anual de turistas (%)",
                            labels={"crescimento_pct": "Variação (%)", "ano": "Ano"})
            st.plotly_chart(figura, width="stretch")

    melhor_ano = anual.loc[anual["turistas"].idxmax()]
    pior_ano = anual.loc[anual["turistas"].idxmin()]
    st.info(
        f"**Interpretação.** No recorte selecionado, o maior fluxo ocorreu em **{int(melhor_ano['ano'])}** "
        f"({abreviar(melhor_ano['turistas'])} turistas) e o menor em **{int(pior_ano['ano'])}** "
        f"({abreviar(pior_ano['turistas'])}). A média móvel de 3 meses suaviza as oscilações sazonais "
        "e deixa a tendência de longo prazo mais visível."
    )

# --- Regiões -----------------------------------------------------------------
with abas[1]:
    st.subheader("Comparação regional")

    por_regiao = dados.groupby("regiao", as_index=False).agg(
        turistas=("turistas", "sum"),
        faturamento=("faturamento_turismo", "sum"),
        ocupacao=("ocupacao_hoteleira", "mean"),
    ).sort_values("turistas", ascending=False)

    esquerda, direita = st.columns(2)
    with esquerda:
        figura = px.bar(por_regiao, x="regiao", y="turistas", color="regiao", template="plotly_white",
                        title="Turistas por região", labels={"regiao": "Região", "turistas": "Turistas"})
        figura.update_layout(showlegend=False)
        st.plotly_chart(figura, width="stretch")
    with direita:
        figura = px.bar(por_regiao.sort_values("faturamento", ascending=False), x="regiao",
                        y="faturamento", color="regiao", template="plotly_white",
                        title="Faturamento por região (R$)",
                        labels={"regiao": "Região", "faturamento": "Faturamento (R$)"})
        figura.update_layout(showlegend=False)
        st.plotly_chart(figura, width="stretch")

    evolucao_regiao = dados.groupby(["ano", "regiao"], as_index=False)["turistas"].sum()
    figura = px.line(evolucao_regiao, x="ano", y="turistas", color="regiao", markers=True,
                     template="plotly_white", title="Evolução de turistas por região",
                     labels={"turistas": "Turistas", "ano": "Ano", "regiao": "Região"})
    st.plotly_chart(figura, width="stretch")

    maior_receita = por_regiao.sort_values("faturamento", ascending=False).iloc[0]
    if por_regiao.iloc[0]["regiao"] == maior_receita["regiao"]:
        frase_regiao = (
            f"A região **{maior_receita['regiao']}** lidera tanto em número de turistas quanto em faturamento "
            f"({abreviar(maior_receita['faturamento'], 'R$ ')})."
        )
    else:
        frase_regiao = (
            f"A região **{por_regiao.iloc[0]['regiao']}** concentra o maior número de turistas, enquanto "
            f"**{maior_receita['regiao']}** lidera em faturamento ({abreviar(maior_receita['faturamento'], 'R$ ')})."
        )
    st.info(
        f"**Interpretação.** {frase_regiao} Comparar os dois gráficos mostra se volume de visitantes e receita "
        "andam juntos entre as regiões ou se o gasto por turista muda o ranking."
    )

# --- Destinos ----------------------------------------------------------------
with abas[2]:
    st.subheader("Ranking e crescimento dos destinos")

    quantidade = st.slider("Quantidade de cidades no ranking", 3, 20, 10)
    ranking = (
        dados.groupby(["cidade", "uf"], as_index=False)
        .agg(turistas=("turistas", "sum"), faturamento=("faturamento_turismo", "sum"),
             ocupacao=("ocupacao_hoteleira", "mean"))
        .sort_values("turistas", ascending=False)
    )

    figura = px.bar(ranking.head(quantidade).sort_values("turistas"), x="turistas", y="cidade",
                    orientation="h", template="plotly_white", title=f"Top {quantidade} cidades por turistas",
                    labels={"turistas": "Turistas", "cidade": "Cidade"})
    st.plotly_chart(figura, width="stretch")

    anos_filtrados = sorted(dados["ano"].unique())
    if len(anos_filtrados) >= 2:
        primeiro, ultimo = anos_filtrados[0], anos_filtrados[-1]
        comparativo = dados[dados["ano"].isin([primeiro, ultimo])].pivot_table(
            index="cidade", columns="ano", values="turistas", aggfunc="sum"
        ).dropna()
        comparativo["crescimento_pct"] = (comparativo[ultimo] / comparativo[primeiro] - 1) * 100
        comparativo = comparativo.sort_values("crescimento_pct", ascending=False).reset_index()
        figura = px.bar(comparativo.head(quantidade), x="cidade", y="crescimento_pct",
                        template="plotly_white",
                        title=f"Maior crescimento de turistas: {primeiro} → {ultimo} (%)",
                        labels={"crescimento_pct": "Crescimento (%)", "cidade": "Cidade"})
        st.plotly_chart(figura, width="stretch")
        destaque = comparativo.iloc[0]
        st.info(
            f"**Interpretação.** **{cidade_top}** é o destino mais visitado do recorte. Entre {primeiro} e "
            f"{ultimo}, o maior crescimento foi de **{destaque['cidade']}** "
            f"({formatar_decimal(destaque['crescimento_pct'])}%). Ranking de volume e ranking de crescimento "
            "contam histórias diferentes: um mostra quem já é grande, o outro quem está ganhando espaço."
        )
    else:
        st.info("Selecione pelo menos dois anos para comparar o crescimento entre destinos.")

    tabela_ranking = ranking.rename(columns={
        "cidade": "Cidade", "uf": "UF", "turistas": "Turistas",
        "faturamento": "Faturamento (R$)", "ocupacao": "Ocupação média (%)",
    })
    st.dataframe(
        tabela_ranking.style.format({
            "Turistas": "{:,.0f}", "Faturamento (R$)": "{:,.0f}", "Ocupação média (%)": "{:.1f}",
        }),
        width="stretch", hide_index=True,
    )

# --- Sazonalidade ------------------------------------------------------------
with abas[3]:
    st.subheader("Sazonalidade turística")

    mapa_calor = dados.pivot_table(index="ano", columns="mes", values="turistas", aggfunc="sum")
    mapa_calor.columns = [NOMES_MESES[m] for m in mapa_calor.columns]
    figura = px.imshow(mapa_calor, aspect="auto", color_continuous_scale="YlOrRd",
                       labels=dict(x="Mês", y="Ano", color="Turistas"),
                       title="Mapa de calor: turistas por mês e ano")
    st.plotly_chart(figura, width="stretch")

    esquerda, direita = st.columns(2)
    with esquerda:
        figura = px.bar(media_mensal, x="nome_mes", y="turistas", template="plotly_white",
                        title="Média de turistas por mês (por registro)",
                        labels={"nome_mes": "Mês", "turistas": "Média de turistas"})
        st.plotly_chart(figura, width="stretch")
    with direita:
        por_temporada = dados.groupby("nivel_temporada", observed=True, as_index=False)["turistas"].sum()
        figura = px.pie(por_temporada, names="nivel_temporada", values="turistas", hole=0.45,
                        title="Turistas por nível de temporada")
        st.plotly_chart(figura, width="stretch")

    meses_pico = media_mensal.sort_values("turistas", ascending=False).head(3)["nome_mes"].tolist()
    mes_vale = media_mensal.sort_values("turistas").iloc[0]["nome_mes"]
    if amplitude_sazonal >= 15:
        texto_sazonal = (
            f"Os meses de maior movimento no recorte são **{', '.join(meses_pico)}** (candidatos naturais à alta "
            f"temporada), e o mais fraco é **{mes_vale}**. A diferença entre o mês mais forte e o mais fraco é de "
            f"{formatar_decimal(amplitude_sazonal)}% da média mensal, o que indica sazonalidade relevante."
        )
    else:
        texto_sazonal = (
            f"O mês de maior movimento médio é **{meses_pico[0]}** e o mais fraco é **{mes_vale}**, mas a diferença "
            f"entre eles é de apenas {formatar_decimal(amplitude_sazonal)}% da média mensal. Isso indica "
            "**pouca sazonalidade** nesta base: o fluxo de turistas é bem distribuído ao longo do ano."
        )
    st.info(
        f"**Interpretação.** {texto_sazonal} O mapa de calor ajuda a verificar se o padrão se repete todos os "
        "anos ou se algum ano fugiu da regra."
    )

    media_nivel = dados.groupby("nivel_temporada", observed=True)["turistas"].mean()
    if {"Alta", "Baixa"}.issubset(media_nivel.index) and media_nivel["Alta"] <= media_nivel["Baixa"]:
        st.warning(
            "**Atenção:** nesta base, o rótulo `nivel_temporada` não acompanha o volume de turistas: a média de "
            f"turistas nos registros de temporada **Alta** ({abreviar(media_nivel['Alta'])}) não é maior que na "
            f"**Baixa** ({abreviar(media_nivel['Baixa'])}). Por isso, a alta temporada foi analisada também pelos "
            "meses, e não apenas pelo rótulo."
        )

# --- Economia e clima --------------------------------------------------------
with abas[4]:
    st.subheader("Impacto econômico e relação com o clima")

    amostra = dados if len(dados) <= 5000 else dados.sample(5000, random_state=1)

    esquerda, direita = st.columns(2)
    with esquerda:
        figura = px.scatter(amostra, x="turistas", y="faturamento_turismo", color="regiao",
                            opacity=0.6, template="plotly_white",
                            title="Turistas × faturamento",
                            labels={"turistas": "Turistas", "faturamento_turismo": "Faturamento (R$)",
                                    "regiao": "Região"})
        if len(dados) > 1 and dados["turistas"].nunique() > 1:
            coeficientes = np.polyfit(dados["turistas"], dados["faturamento_turismo"], 1)
            eixo_x = np.linspace(dados["turistas"].min(), dados["turistas"].max(), 50)
            figura.add_trace(go.Scatter(x=eixo_x, y=np.polyval(coeficientes, eixo_x), mode="lines",
                                        name="Tendência linear", line=dict(color="black", dash="dash")))
        st.plotly_chart(figura, width="stretch")
    with direita:
        figura = px.scatter(amostra, x="temperatura_media", y="turistas", color="regiao",
                            opacity=0.6, template="plotly_white",
                            title="Temperatura × turistas",
                            labels={"temperatura_media": "Temperatura média (°C)", "turistas": "Turistas",
                                    "regiao": "Região"})
        st.plotly_chart(figura, width="stretch")

    st.markdown("**Matriz de correlação (Pearson)**")
    matriz = dados[COLUNAS_NUMERICAS].corr()
    matriz.index = [ROTULOS[c] for c in matriz.index]
    matriz.columns = [ROTULOS[c] for c in matriz.columns]
    figura_seaborn, eixo = plt.subplots(figsize=(9, 5))
    sns.heatmap(matriz, annot=True, fmt=".2f", cmap="coolwarm", center=0, linewidths=0.5, ax=eixo)
    eixo.tick_params(axis="x", rotation=40)
    plt.tight_layout()
    st.pyplot(figura_seaborn)
    plt.close(figura_seaborn)

    if abs(correlacao_receita) >= 0.4:
        frase_receita = "mais visitantes tendem a gerar mais receita."
    else:
        frase_receita = "o número de turistas, sozinho, não explica o faturamento nesta base."
    if abs(correlacao_clima) < 0.2:
        frase_clima = "o clima, medido pela temperatura média, não explica o fluxo de turistas."
    else:
        frase_clima = "há uma associação entre temperatura e fluxo de turistas, que pode variar entre regiões."

    st.info(
        f"**Interpretação.** A correlação entre turistas e faturamento é **{classificar(correlacao_receita)}** "
        f"(r = {formatar_decimal(correlacao_receita, 2)}): {frase_receita} "
        f"A relação entre temperatura e turistas é **{classificar(correlacao_clima)}** "
        f"(r = {formatar_decimal(correlacao_clima, 2)}): {frase_clima} "
        "Correlação não implica causalidade; vale filtrar por região e comparar."
    )

# --- Ocupação hoteleira ------------------------------------------------------
with abas[5]:
    st.subheader("Ocupação hoteleira")

    ocupacao_mensal = dados.groupby(["mes", "nome_mes", "regiao"], as_index=False)["ocupacao_hoteleira"].mean()
    figura = px.line(ocupacao_mensal.sort_values("mes"), x="nome_mes", y="ocupacao_hoteleira",
                     color="regiao", markers=True, template="plotly_white",
                     title="Ocupação hoteleira média por mês e região",
                     labels={"nome_mes": "Mês", "ocupacao_hoteleira": "Ocupação (%)", "regiao": "Região"})
    st.plotly_chart(figura, width="stretch")

    esquerda, direita = st.columns(2)
    with esquerda:
        ocupacao_cidade = (dados.groupby("cidade", as_index=False)["ocupacao_hoteleira"].mean()
                           .sort_values("ocupacao_hoteleira", ascending=False).head(10))
        figura = px.bar(ocupacao_cidade.sort_values("ocupacao_hoteleira"), x="ocupacao_hoteleira",
                        y="cidade", orientation="h", template="plotly_white",
                        title="Cidades com maior ocupação média",
                        labels={"ocupacao_hoteleira": "Ocupação (%)", "cidade": "Cidade"})
        st.plotly_chart(figura, width="stretch")
    with direita:
        figura = px.box(dados, x="nivel_temporada", y="ocupacao_hoteleira", template="plotly_white",
                        category_orders={"nivel_temporada": ORDEM_TEMPORADA},
                        title="Ocupação por nível de temporada",
                        labels={"nivel_temporada": "Temporada", "ocupacao_hoteleira": "Ocupação (%)"})
        st.plotly_chart(figura, width="stretch")

    media_por_temporada = dados.groupby("nivel_temporada", observed=True)["ocupacao_hoteleira"].mean()
    if {"Alta", "Baixa"}.issubset(media_por_temporada.index):
        diferenca = media_por_temporada["Alta"] - media_por_temporada["Baixa"]
        if abs(diferenca) >= 3:
            complemento = "Esse intervalo mostra quanta capacidade hoteleira fica ociosa fora da temporada."
        else:
            complemento = ("A diferença é pequena: nesta base, a ocupação hoteleira praticamente não varia "
                           "entre alta e baixa temporada.")
        st.info(
            f"**Interpretação.** A ocupação média é de {formatar_decimal(media_por_temporada['Alta'])}% na "
            f"alta temporada contra {formatar_decimal(media_por_temporada['Baixa'])}% na baixa "
            f"({formatar_decimal(diferenca)} pontos percentuais de diferença). {complemento}"
        )
    else:
        st.info("Inclua os níveis de temporada Alta e Baixa nos filtros para comparar a ocupação.")

# --- Tabela dinâmica ---------------------------------------------------------
with abas[6]:
    st.subheader("Tabela dinâmica")
    st.caption("Monte seu próprio cruzamento de dados a partir do filtro atual.")

    opcoes_agrupamento = ["regiao", "uf", "cidade", "ano", "nome_mes", "trimestre", "nivel_temporada"]
    c1, c2, c3, c4 = st.columns(4)
    linhas = c1.selectbox("Linhas", opcoes_agrupamento, index=0)
    colunas = c2.selectbox("Colunas", ["(nenhuma)"] + opcoes_agrupamento, index=0)
    valor = c3.selectbox("Valor", COLUNAS_NUMERICAS, format_func=lambda c: ROTULOS[c])
    funcao = c4.selectbox("Cálculo", ["sum", "mean", "max", "min", "count"],
                          format_func=lambda f: {"sum": "Soma", "mean": "Média", "max": "Máximo",
                                                 "min": "Mínimo", "count": "Contagem"}[f])

    if colunas == linhas:
        st.warning("Escolha campos diferentes para linhas e colunas.")
    else:
        if colunas == "(nenhuma)":
            tabela = dados.pivot_table(index=linhas, values=valor, aggfunc=funcao, observed=True)
        else:
            tabela = dados.pivot_table(index=linhas, columns=colunas, values=valor,
                                       aggfunc=funcao, observed=True)
        st.dataframe(tabela.style.format("{:,.1f}"), width="stretch")

    st.download_button(
        "Baixar dados filtrados (CSV)",
        data=dados.to_csv(index=False).encode("utf-8"),
        file_name="turismo_filtrado.csv",
        mime="text/csv",
    )

# --- Conclusão executiva -----------------------------------------------------
with abas[7]:
    st.subheader("Conclusão executiva")

    mes_pico = media_mensal.sort_values("turistas", ascending=False).iloc[0]["nome_mes"]
    meses_pico_lista = ", ".join(media_mensal.sort_values("turistas", ascending=False).head(3)["nome_mes"])
    anos_dados = sorted(dados["ano"].unique())

    if amplitude_sazonal >= 15:
        recomendacao_sazonal = (
            f"Concentrar campanhas e capacidade hoteleira nos meses de pico ({meses_pico_lista}) e criar ações "
            "de atração (eventos, pacotes) para a baixa temporada."
        )
        frase_sazonal = f"há sazonalidade relevante (pico em **{mes_pico}**)"
    else:
        recomendacao_sazonal = (
            "Como o fluxo é bem distribuído ao longo do ano, o planejamento de capacidade pode ser mais uniforme "
            "entre os meses; vale investigar fatores locais (eventos, clima regional) para explicar as "
            "diferenças entre as cidades."
        )
        frase_sazonal = f"a sazonalidade é pequena (mês mais forte: **{mes_pico}**)"

    por_regiao_receita = dados.groupby("regiao")[["faturamento_turismo", "turistas"]].sum()
    receita_por_turista = (por_regiao_receita["faturamento_turismo"] / por_regiao_receita["turistas"]).sort_values()
    regiao_menor_gasto = receita_por_turista.index[0]
    regiao_maior_gasto = receita_por_turista.index[-1]
    st.markdown(
        f"""
**O que os dados mostram (recorte atual: {anos_dados[0]}–{anos_dados[-1]}, {len(dados)} registros):**

- **Volume:** foram contabilizados **{abreviar(total_turistas)} turistas**, com maior concentração em
  **{cidade_top}** (cidade) e na região **{regiao_top}**.
- **Impacto econômico:** o setor gerou **{abreviar(receita_total, 'R$ ')}** em receita, com gasto médio de
  **{abreviar(gasto_medio, 'R$ ')}** por turista.
- **Sazonalidade:** {frase_sazonal}, e a ocupação hoteleira média do período é de
  **{formatar_decimal(ocupacao_media)}%**.
- **Relação turistas × receita:** correlação {classificar(correlacao_receita)}
  (r = {formatar_decimal(correlacao_receita, 2)}).

**Recomendações:**

1. {recomendacao_sazonal}
2. Acompanhar os destinos de maior crescimento como oportunidades de investimento em infraestrutura.
3. Comparar a receita por turista entre as regiões: **{regiao_maior_gasto}** tem o maior valor
   ({abreviar(receita_por_turista.iloc[-1], 'R$ ')}) e **{regiao_menor_gasto}** o menor
   ({abreviar(receita_por_turista.iloc[0], 'R$ ')}); estimular serviços de maior valor agregado onde o
   gasto por visitante é menor.

*Observação: os dados são simulados e têm finalidade educacional; as conclusões ilustram o método de
análise e não representam estatísticas oficiais do turismo brasileiro.*
"""
    )

st.caption("Projeto G2 · Tema 18 · Análise e Visualização de Dados com Python")
