---
title: Sentix FinBERT
emoji: 📊
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: mit
short_description: Análise de Sentimento Financeiro Brasileiro
---

# 🇧🇷 Sentix FinBERT

**Análise de Sentimento para Notícias Financeiras Brasileiras**

Este Space utiliza o modelo [FinBERT](https://huggingface.co/ProsusAI/finbert) para analisar o sentimento de textos financeiros em português.

## 🚀 Funcionalidades

- **Análise Única**: Analise um texto por vez
- **Análise em Lote**: Processe até 10 textos simultaneamente
- **API**: Integre com outros serviços

## 📊 Output

- **Score**: -1 (muito negativo) a +1 (muito positivo)
- **Probabilidades**: Positivo, Neutro, Negativo

## 🔌 API Usage

```python
from gradio_client import Client

client = Client("seu-usuario/sentix-finbert")
result = client.predict(
    text="Petrobras anuncia lucro recorde",
    api_name="/predict"
)
print(result)
```

## 📝 Exemplos

| Texto | Sentimento | Score |
|-------|------------|-------|
| "Ações sobem após balanço positivo" | Positivo | +0.65 |
| "Inflação preocupa investidores" | Negativo | -0.42 |
| "Mercado aguarda decisão do Fed" | Neutro | +0.05 |

---

Desenvolvido como parte do projeto **Sentix** para análise probabilística de mercado.
