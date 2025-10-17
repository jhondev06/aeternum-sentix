# Sentix-FinBERT MVP - Instruções de Uso

## Introdução

O Sentix-FinBERT é um pipeline de análise de sentimento para finanças que utiliza o modelo FinBERT para processar notícias e prever movimentos de preços. O sistema ingere feeds RSS, analisa sentimentos, agrega features em buckets temporais, treina um modelo calibrado e fornece uma API para pontuação em tempo real.

## Estrutura do Projeto

```
sentix/
├─ config.yml              # Configurações principais
├─ requirements.txt        # Dependências Python
├─ tickers.yml            # Mapeamento de tickers
├─ main.py                # Orquestrador principal
├─ data/                  # Dados processados
├─ outputs/               # Resultados e modelos treinados
├─ ingest/                # Módulos de ingestão RSS
├─ sentiment/             # Análise de sentimento com FinBERT
├─ features/              # Agregação de features
├─ backtest/              # Rotulagem e backtesting
├─ models/                # Modelo de probabilidade
├─ api/                   # API FastAPI
└─ notify/                # Notificações Telegram
```

## Instalação

Recomendado: Python 3.11 (Windows) para evitar compilação de pacotes.

1. **Criar ambiente virtual (opcional, recomendado):**
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   ```

2. **Instalar dependências:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Verificar instalação:**
   ```bash
   python -c "import transformers, torch; print('Instalação OK')"
   ```

## Configuração

### Arquivo config.yml
- `data.languages`: Idiomas permitidos (ex: ["en", "pt"])
- `data.min_chars`: Comprimento mínimo do texto
- `data.rss_feeds`: Lista de feeds RSS
- `data.price.symbols`: Tickers para análise
- `sentiment.model_id`: Modelo FinBERT
- `aggregation.window`: Janela de agregação (ex: "60min")
- `signals.threshold_long`: Limite para sinal de compra

### Arquivo tickers.yml
Adicione novos tickers e aliases:
```yaml
TSLA:
  aliases: ["Tesla", "NASDAQ:TSLA", "TSLA"]
```

## Execução

### Pipeline Completo
```bash
cd sentix
python main.py
```

Este comando executará:
1. Ingestão de RSS
2. Normalização e mapeamento
3. Agregação de features
4. Rotulagem com preços
5. Treinamento do modelo
6. Backtesting
7. Geração de relatórios

### API em Tempo Real
```bash
uvicorn api.app:app --reload
```

### Teste da API
```bash
# Pontuar texto
curl -X POST http://127.0.0.1:8000/score_text \
  -H "Content-Type: application/json" \
  -d '{"text":"Apple supera expectativas; guidance forte.","ticker":"AAPL"}'

# Obter sinal
curl http://127.0.0.1:8000/signal?ticker=AAPL
```

### Integração com sistemas externos (Webhooks)

O Sentix inclui um sistema de alertas que pode enviar notificações para sistemas externos (monitoramento/analytics) via webhooks.

#### 1. Configurar Webhook
```bash
curl -X POST "http://localhost:8000/alerts/webhooks" \
  -H "Content-Type: application/json" \
  -u "admin:sentix123" \
  -d '{"url": "https://your-webhook-endpoint.com/alerts", "enabled": true}'
```

#### 2. Criar Regras de Alerta
```bash
curl -X POST "http://localhost:8000/alerts/rules" \
  -H "Content-Type: application/json" \
  -u "admin:sentix123" \
  -d '{
    "rule_id": "sentiment_alert",
    "name": "Alerta de Sentimento",
    "ticker": "PETR4.SA",
    "conditions": [{"field": "mean_sent", "operator": ">", "value": 0.5}],
    "actions": [{"type": "webhook", "url": "https://your-webhook-endpoint.com/alerts"}]
  }'
```

#### 3. Testar processamento de alertas
```bash
curl -X POST "http://localhost:8000/alerts/process" -u "admin:sentix123"
```

### Notificações Telegram
1. Configure `telegram.enabled: true` e adicione `token` e `chat_id` em config.yml
2. Execute: `python notify/telegram.py`

## Saídas Geradas

Após execução, os seguintes arquivos serão criados:

- `data/articles_raw.csv`: Artigos processados
- `data/sentiment_bars.csv`: Features agregadas
- `data/training_set.csv`: Dataset de treinamento
- `outputs/prob_model.pkl`: Modelo treinado
- `outputs/equity.png`: Curva de equity do backtest
- `outputs/report.md`: Relatório de métricas

## Próximos Passos

### 1. Customização
- Adicione mais feeds RSS em config.yml
- Configure novos tickers em tickers.yml
- Ajuste parâmetros de agregação e sinais

### 2. Produção
- Configure um scheduler (ex: cron) para executar main.py periodicamente
- Deploy da API em servidor (ex: Heroku, AWS)
- Configure monitoramento e alertas

### 3. Melhorias
- Adicione mais features (ex: volume, volatilidade)
- Implemente ensemble de modelos
- Adicione dashboard Streamlit para visualização

### 4. Expansão
- Suporte a mais idiomas
- Integração com outras fontes de dados
- Análise de sentimento em tempo real

## Troubleshooting

### Problemas Comuns

1. **Erro de instalação do Torch:**
   - Use CPU wheel oficial se GPU não estiver disponível
   - `pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu`

2. **Poucos artigos:**
   - Adicione mais feeds RSS
   - Reduza `min_chars` para 80
   - Execute múltiplas vezes por dia

3. **Modelo não carrega:**
   - Verifique conexão com internet
   - Modelo será baixado automaticamente na primeira execução

4. **API não responde:**
   - Verifique se uvicorn está rodando
   - Confirme porta 8000 não está ocupada

### Logs
O sistema usa logging. Para debug:
```bash
python main.py 2>&1 | tee log.txt
```

## Suporte

Para dúvidas ou problemas:
1. Verifique os logs
2. Teste componentes individualmente
3. Ajuste configurações gradualmente

O sistema é determinístico e configurável, permitindo iterações rápidas.