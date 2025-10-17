# Dossiê do Projeto Sentix

Este documento resume, de forma executiva e auditável, o objetivo do projeto, arquitetura técnica, fluxo de dados, principais componentes, limitações, e instruções de uso para tomada de decisão por economistas e investidores.

## Objetivo
Fornecer uma ferramenta quantitativa que, antes da compra de um ativo, estime a probabilidade de subir ou descer com base em sentimento de notícias e sinais calibrados. O sistema expõe probabilidades, componentes utilizados e um endpoint operacional de “sinal” (long/short/hold).

## Arquitetura em alto nível
- Ingestão de dados: RSS/Twitter captura artigos (ingest/rss_client.py, ingest/twitter_client.py).
- Normalização: mapeia entidades/tickers nos textos (ingest/normalize.py, tickers.yml).
- Sentimento: FinBERT para prob. pos/neg/neu e score (sentiment/finbert.py).
- Agregação: barras de sentimento por ticker e janela (features/aggregate.py) → data/sentiment_bars.csv.
- Preços e rótulos: baixa yfinance, calcula retorno futuro e rótulos binários (backtest/label.py) → data/training_set.csv.
- Modelo probabilístico: LogisticRegression calibrada (models/prob_model.py) → outputs/prob_model.pkl.
- API e Alertas: FastAPI com endpoints de consulta e sistema de alertas (api/app.py, alerts/*).
- Dashboard: Visualização e controle (dashboard.py).
- Integração externa via webhooks: Notificações para sistemas de monitoramento/analytics.

## Fluxo principal de dados
1) Capturar artigos → filtrar por idioma e tamanho mínimo.
2) Extrair tickers via regex/aliases → explode por ticker.
3) Inferir sentimento por artigo → pos/neg/neu/score.
4) Agregar por janelas (config.yml) → estatísticas por ticker (mean/std/min/max/count/unc/decay).
5) Unir com preços → gerar training_set com labels (y) e r_fwd.
6) Treinar modelo probabilístico → salvar outputs/prob_model.pkl.
7) Servir API/Alertas/Dashboard.

## Componentes principais
- sentiment/finbert.py: classe FinBertSentiment para predição batelada.
- features/aggregate.py: build_sentiment_bars cria barras agregadas por ticker.
- backtest/label.py: cria conjunto de treinamento unindo sentimento e preços.
- models/prob_model.py: ProbModel com CalibratedClassifierCV. Preserva a ordem de features do treino (feature_cols) e reindexa na predição para evitar mismatch.
- api/app.py: Endpoints de consulta e alertas.
- alerts/engine.py, alerts/rule.py, alerts/webhook.py, alerts/logger.py: motor de regras, ações e auditoria.
- dashboard.py: visualização das séries e estatísticas.
- mock_hft_system.py: servidor Flask para simulação de execução de trades.

## Endpoints da API (principais)
- POST /score_text: dado um texto (e opcionalmente um ticker), retorna prob_up baseada no sentimento FinBERT + componentes pos/neg/neu/score.
- GET /probabilities?ticker=XYZ: retorna prob_up/prob_down para o ticker, componentes de sentimento mais recentes e features efetivamente utilizadas pelo modelo.
- GET /signal?ticker=XYZ: decisão operacional (long/short/hold) com base em thresholds do config.yml.
- GET /realtime, /historical: séries agregadas por ticker.

Autenticação: HTTP Basic (config.yml → api.auth). Use credenciais padrão apenas para testes.

## Dados e Configurações
- config.yml: 
  - Data: idiomas, feeds RSS, parâmetros do Twitter.
  - Price: símbolos, intervalo e período para yfinance.
  - Sentiment: modelo FinBERT e batch_size.
  - Aggregation: janela (ex.: W-MON) e half-life de decaimento.
  - Model: tipo, horizonte e calibração.
  - Signals: thresholds, custos e cooldown.
  - Alerts/Telegram/API: toggles e credenciais.
- tickers.yml: mapa de tickers ↔ aliases (ex.: PETR4.SA ↔ Petrobras).
- data/: arquivos CSV gerados (articles_raw, sentiment_bars, training_set, etc.).

## Backtesting e Métricas
- backtest/backtester.py: calcula PnL, equity curve, AUC, Brier, win rate, Sharpe, MDD, retorno total. Ajuda a calibrar thresholds e avaliar robustez do modelo.

## Alertas
- Definição de regras por condições (GREATER_THAN, LESS_THAN, CROSS_ABOVE, etc.) com cooldown e ações (webhook/Telegram/log).
- Persistência: data/alert_rules.json, data/webhooks.json; logs diários em logs/alerts.

## Integração externa (Webhooks)
Envia alertas para endpoints configurados, com registro de entregas e histórico de alertas.