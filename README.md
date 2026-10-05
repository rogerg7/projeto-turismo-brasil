# 🧭 Turismo no Brasil (2015–2024)

Projeto G2 · Tema 18 · Análise e Visualização de Dados com Python

Análise e dashboard interativo de uma base **simulada** de turismo no Brasil, para investigar destinos mais
visitados, sazonalidade, comparação entre regiões, impacto econômico e ocupação hoteleira.

## Links

| O quê | Onde |
| --- | --- |
| Código-fonte (GitHub) | https://github.com/SEU_USUARIO/projeto-turismo-brasil |
| Página do projeto (GitHub Pages) | https://SEU_USUARIO.github.io/projeto-turismo-brasil/ |
| Dashboard (Streamlit Cloud) | https://SEU-APP.streamlit.app/ |

## Perguntas respondidas

1. Quais cidades recebem mais turistas?
2. Existem períodos de alta temporada?
3. Quais regiões movimentam mais recursos?
4. Qual o impacto econômico do turismo?
5. Existem diferenças regionais relevantes?
6. Quais destinos apresentaram maior crescimento?
7. Como o turismo evoluiu ao longo do tempo?

## Tecnologias

Python · Pandas · NumPy · Plotly · Matplotlib · Seaborn · Streamlit · SQLAlchemy · SQLite · GitHub · GitHub Pages

## Estrutura do projeto

```
projeto-turismo-brasil/
├── app.py                          # dashboard Streamlit
├── requirements.txt                # dependências
├── README.md
├── index.html                      # página do projeto (GitHub Pages)
├── dados/
│   └── simulacao_turismo_brasil.csv
├── notebooks/
│   └── analise_turismo.ipynb       # análise exploratória completa
├── database/                       # banco SQLite (turismo.db), criado a partir do CSV
└── imagens/                        # gráficos exportados pelo notebook
```

## Como funciona

1. O `app.py` lê o CSV, faz o **tratamento** (duplicatas, nulos, tipos, padronização) e a **engenharia de
   atributos** (`nome_mes`, `trimestre`, `pct_estrangeiros`, `faturamento_por_turista`).
2. A base tratada é gravada em **SQLite com SQLAlchemy** (`database/turismo.db`) e o dashboard lê os dados
   direto do banco. Se o CSV for atualizado, o banco é recriado automaticamente.
3. O dashboard aplica os filtros e atualiza KPIs, gráficos e textos de interpretação.

## Dashboard

**Filtros:** ano, mês, região, estado, cidade e nível de temporada.

**KPIs:** total de turistas, receita total, cidade mais visitada, ocupação hoteleira média, gasto médio por
turista e região mais movimentada.

**Seções:**

- Evolução temporal (com média móvel de 3 meses e crescimento anual)
- Comparação regional
- Ranking e crescimento de destinos
- Sazonalidade (mapa de calor mensal)
- Economia e clima (dispersão turistas × faturamento e matriz de correlação)
- Ocupação hoteleira
- Tabela dinâmica configurável, com download do recorte em CSV
- Conclusão executiva

Cada seção traz uma interpretação textual que se atualiza conforme os filtros.

## Funcionalidades além do básico

- **Intermediárias:** filtros múltiplos, KPIs dinâmicos, análise temporal, dashboard organizado em seções,
  visualizações comparativas.
- **Avançadas:** persistência em banco (SQLAlchemy + SQLite), correlação estatística (Pandas/NumPy) e séries
  temporais avançadas (média móvel e variação anual).

## Como executar localmente

```bash
# 1. Clonar o repositório
git clone https://github.com/SEU_USUARIO/projeto-turismo-brasil.git
cd projeto-turismo-brasil

# 2. (Opcional) criar um ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Instalar as dependências
pip install -r requirements.txt

# 4. Rodar o dashboard
streamlit run app.py
```

Para explorar o notebook: abra `notebooks/analise_turismo.ipynb` no Jupyter ou no Google Colab
(no Colab, envie também o arquivo `simulacao_turismo_brasil.csv`).

## Publicação

- **GitHub:** repositório com todo o código e a base de dados.
- **GitHub Pages:** *Settings → Pages → Deploy from a branch → `main` / `(root)`*. A página inicial é o `index.html`.
- **Streamlit Community Cloud:** em [share.streamlit.io](https://share.streamlit.io), crie um app apontando
  para o repositório, branch `main` e arquivo principal `app.py`.

## Sobre os dados

Base simulada (`simulacao_turismo_brasil.csv`: 4.440 registros, 37 cidades, jan/2015 a dez/2024), fornecida pelo professor no repositório [AlexandreLouzada/Dados-Simulados-G2](https://github.com/AlexandreLouzada/Dados-Simulados-G2) e usada sem edições. As conclusões ilustram o método de análise e não representam
estatísticas oficiais do turismo brasileiro.

## Autor

Roger · Sistemas de Informação, Universidade La Salle
