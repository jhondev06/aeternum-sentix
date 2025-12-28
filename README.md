# Sentix — Análise de Sentimento Financeiro com FinBERT

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red)
![HuggingFace](https://img.shields.io/badge/🤗%20HuggingFace-Spaces-yellow)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-green)
![Deploy](https://img.shields.io/badge/Deploy-Render-purple)

**Sentix** é uma plataforma completa de análise de sentimento para o mercado financeiro brasileiro, utilizando **FinBERT** fine-tuned para português. O sistema combina Machine Learning, deploy em nuvem e persistência de dados para entregar análises em tempo real.

## 🚀 Live Demo

- **Dashboard**: [sentix-dashboard.onrender.com](https://sentix-dashboard.onrender.com)
- **Modelo FinBERT**: [huggingface.co/spaces/bitek/sentix-finbert](https://huggingface.co/spaces/bitek/sentix-finbert)

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USUÁRIO                                     │
│                            │                                        │
│                            ▼                                        │
│    ┌─────────────────────────────────────────┐                     │
│    │   DASHBOARD (Render - Streamlit)        │                     │
│    │   - Interface Cyberpunk/Glassmorphism   │                     │
│    │   - Seleção de Ativos                   │                     │
│    │   - Visualização de Gráficos            │                     │
│    └─────────────────────────────────────────┘                     │
│                            │                                        │
│              Gradio Client │                                        │
│                            ▼                                        │
│    ┌─────────────────────────────────────────┐                     │
│    │   FINBERT API (HuggingFace Spaces)      │                     │
│    │   - Modelo: ProsusAI/finbert            │                     │
│    │   - Fine-tuned para PT-BR               │                     │
│    │   - Inferência GPU/CPU                  │                     │
│    └─────────────────────────────────────────┘                     │
│                            │                                        │
│                            ▼                                        │
│    ┌─────────────────────────────────────────┐                     │
│    │   SUPABASE (PostgreSQL)                 │                     │
│    │   - Histórico de análises               │                     │
│    │   - Dados por ticker                    │                     │
│    └─────────────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────┘
```

## ✨ Features

### Dashboard
- 🎨 **Tema Cyberpunk** com glassmorphism e animações
- 📊 **Gráficos interativos** com Plotly
- 🏷️ **Seleção de ativos** por categoria (Ações, ETFs, FIIs)
- 📈 **Métricas em tempo real** (Prob. Subida, Sentimento Médio)
- 💾 **Persistência** no Supabase

### Machine Learning
- 🧠 **FinBERT** - Modelo BERT treinado em textos financeiros
- 🇧🇷 **Fine-tuning PT-BR** - Otimizado para português brasileiro
- 📊 **3 classes** - Positivo, Negativo, Neutro
- 🔄 **Inferência via API** - HuggingFace Spaces

### Infraestrutura
- ☁️ **Deploy Render** - Dashboard + API
- 🤗 **HuggingFace Spaces** - Modelo FinBERT
- 🐘 **Supabase** - PostgreSQL gerenciado
- 🔒 **Environment Variables** - Configuração segura

## 📁 Estrutura do Projeto

```
sentix/
├── api/
│   ├── app.py              # FastAPI completa
│   └── app_light.py        # API leve para Render
├── sentiment/
│   └── finetune_finbert.py # Fine-tuning para PT-BR
├── data/
│   ├── training_set.csv    # Dataset de treino
│   └── demo_training_set.csv
├── database.py             # SQLAlchemy + Supabase
├── dashboard_render.py     # Dashboard Streamlit (produção)
├── dashboard.py            # Dashboard local
├── telegram.py             # Alertas Telegram
├── scheduler.py            # APScheduler (RSS, preços)
├── config.yml              # Configurações
└── requirements-render.txt # Deps para deploy
```

## 🛠️ Stack Tecnológica

| Componente | Tecnologia |
|------------|------------|
| **ML Model** | FinBERT (transformers) |
| **Frontend** | Streamlit |
| **Backend** | FastAPI |
| **Database** | PostgreSQL (Supabase) |
| **Hosting** | Render + HuggingFace |
| **ORM** | SQLAlchemy |
| **Charts** | Plotly |

## 🚀 Quick Start

### Local
```bash
# Clonar repositório
git clone https://github.com/jhondev06/aeternum-sentix.git
cd aeternum-sentix

# Instalar dependências
pip install -r sentix/requirements.txt

# Rodar dashboard local
streamlit run sentix/dashboard.py
```

### Fine-tuning (opcional)
```bash
# Treinar modelo com dataset demo
python sentix/sentiment/finetune_finbert.py --demo

# Treinar com dataset customizado
python sentix/sentiment/finetune_finbert.py --data data/training_set.csv
```

## ⚙️ Variáveis de Ambiente

No Render, configure:

```bash
DATABASE_URL=postgresql://postgres.XXX:PASSWORD@aws-0-sa-east-1.pooler.supabase.com:6543/postgres
HF_SPACE_URL=https://bitek-sentix-finbert.hf.space
PYTHON_VERSION=3.11.4
```

## 📊 Ativos Suportados

### Ações
- PETR4.SA, VALE3.SA, ITUB4.SA, BBDC4.SA, ABEV3.SA
- WEGE3.SA, RENT3.SA, MGLU3.SA, BBAS3.SA, B3SA3.SA

### ETFs
- BOVA11.SA, SMAL11.SA, IVVB11.SA

### FIIs
- HGLG11.SA, MXRF11.SA, XPLG11.SA

## 🎯 Roadmap

- [x] Dashboard Streamlit com tema cyberpunk
- [x] Integração FinBERT via HuggingFace Spaces
- [x] Persistência PostgreSQL (Supabase)
- [x] Deploy Render (Dashboard + API)
- [x] Fine-tuning script para PT-BR
- [ ] Testes automatizados (coverage > 80%)
- [ ] Observabilidade (Sentry/Datadog)
- [ ] Autenticação de usuários
- [ ] Fine-tuning completo em produção

## 📄 Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

## 👨‍💻 Autor

Desenvolvido por **[jhondev06](https://github.com/jhondev06)**

---

*Sentix - Transformando notícias em insights acionáveis* 📈