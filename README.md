# Sentix — MVP de Análise de Sentimento (PT-BR)

Sentix é um pipeline de análise de sentimento para finanças usando FinBERT. Ele ingere notícias (RSS), processa sentimento, gera features por bucket temporal, treina um modelo calibrado (Logistic + Isotonic) e expõe uma API e um dashboard para exploração.

Foco: análise de sentimento e probabilidades — sem execução de ordens, sem integração com sistemas de trading.

## Principais componentes
- Ingestão: RSS (feedparser) e normalização/mapeamento de tickers
- Sentimento: FinBERT (transformers/torch), batched
- Features: agregação em buckets (mean/std/min/max/count/unc/time_decay)
- Modelo: LogReg + isotonic calibration (scikit-learn)
- API: FastAPI com autenticação básica
- Dashboard: Streamlit com KPIs, gráficos e correlações
- Alertas: regras e webhooks genéricos (monitoramento/analytics)

## Requisitos de ambiente
- Python 3.11 recomendado (Windows)
- Pacotes: ver `sentix/requirements.txt`
- GPU opcional (FinBERT roda em CPU)

## Quick Start (Windows)
1) Preparar dados demo e treinar modelo
- PowerShell:
  - `sentix\run_demo.ps1`

2) Iniciar o dashboard
- PowerShell:
  - `sentix\run_dashboard.ps1`
- Abre em: http://localhost:8501

3) Iniciar a API
- PowerShell:
  - `sentix\run_api.ps1`
- Base URL: http://localhost:8000
- Auth: `admin` / `sentix123` (configurável em `sentix/config.yml`)

## Estrutura do projeto
```
sentix/
├─ config.yml               # Configurações principais
├─ requirements.txt         # Dependências
├─ tickers.yml              # Mapeamento de aliases por ticker
├─ data/                    # Dados processados (CSV)
├─ outputs/                 # Modelo e relatórios
├─ ingest/                  # RSS e normalização
├─ sentiment/               # FinBERT
├─ features/                # Agregação de features
├─ backtest/                # Labels e backtest
├─ models/                  # Modelo de probabilidade
├─ api/                     # FastAPI
├─ notify/                  # Telegram (opcional)
├─ dashboard.py             # Streamlit
└─ init_model.py            # Gera demo + treina
```

## Configuração
- `sentix/config.yml`: idiomas, feeds, janela de agregação, limites de sinal, auth da API.
- `sentix/tickers.yml`: aliases para mapear menções a tickers.

## Troubleshooting
- Torch/Transformers: sem GPU, instale roda CPU (já contemplado no requirements).
- Numpy/Scikit-learn no Windows: use Python 3.11 (evita builds complexos). 
- Poucos artigos: adicione feeds em `config.yml` e ajuste `min_chars`.
- API não inicia por import: rode com cwd `sentix/` ou use `run_api.ps1`.

## Deploy
- Guia de deploy em VPS/Render: `sentix/docs/deployment_render.md`
- Dockerfile pronto com healthcheck e inicialização (`init_model.py`).

## Privacidade e foco
- O pacote distribuído ao usuário final não contém referências a HFT.
- Alertas usam webhooks genéricos para monitoramento/analytics.

## Licença
- MIT License (ver arquivo LICENSE).

## Suporte
- Consulte `sentix/instruction.md` e `sentix/docs/api_documentation.md` para detalhes adicionais.