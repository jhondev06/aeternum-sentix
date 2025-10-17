# Sentix‑FinBERT MVP — Step‑by‑Step Build Guide (for O3)

**Goal:** Build a production‑ready **news sentiment → probability of up‑move** pipeline using **FinBERT** (transformers) that runs **in parallel to AXON** (no code changes inside AXON). The output is (a) a calibrated probability per ticker & time bucket and (b) a minimal REST API / Telegram alert for demo.

**Non‑Goals:** Deep infra, high‑freq ingestion, model zoo, cloud deploy. Keep it fast and shippable today.

---

## 0) Assumptions
- Python 3.10+
- CPU only is fine (FinBERT on transformers). If GPU exists, use automatically.
- Data sources: RSS feeds (free) for MVP. YFinance for prices.
- Run **outside** AXON; optionally export features to a CSV AXON can read later.

---

## 1) Project Layout
```
sentix/
├─ config.yml
├─ requirements.txt
├─ tickers.yml
├─ data/
│  ├─ articles_raw.csv           # out: deduped articles with mapped tickers
│  └─ sentiment_bars.csv         # out: aggregated features per ticker & bucket
├─ outputs/
│  ├─ prob_model.pkl             # trained calibrated model
│  ├─ equity.png                 # backtest equity curve
│  └─ report.md                  # backtest & calibration summary
├─ ingest/
│  ├─ rss_client.py              # pull RSS
│  └─ normalize.py               # lang detect, dedupe, ticker mapping
├─ sentiment/
│  └─ finbert.py                 # FinBERT inference (batched)
├─ features/
│  └─ aggregate.py               # bucketize + features
├─ backtest/
│  ├─ label.py                   # align prices, build labels
│  └─ backtester.py              # event‑driven test & metrics
├─ models/
│  └─ prob_model.py              # logistic + isotonic calibration
├─ api/
│  └─ app.py                     # FastAPI for demo
├─ notify/
│  └─ telegram.py                # optional alerts (threshold)
└─ main.py                       # end‑to‑end runner
```

---

## 2) Requirements
Create `requirements.txt`:
```txt
pandas>=2.2
numpy>=1.26
scikit-learn>=1.5
PyYAML>=6.0
feedparser>=6.0
langdetect>=1.0.9
yfinance>=0.2
fastapi>=0.111
uvicorn[standard]>=0.30
python-telegram-bot>=21.4
transformers>=4.43
torch>=2.3
requests>=2.32
```
> Note (Windows CPU): if `torch` wheels fail, install CPU wheel from the official index (no CUDA).

Install:
```bash
python -m pip install -r requirements.txt
```

---

## 3) Configuration
Create `config.yml`:
```yaml
data:
  languages: ["en", "pt"]
  min_chars: 120
  rss_feeds:
    - "https://www.marketwatch.com/rss/topstories"
    - "https://www.infomoney.com.br/feed/"
  price:
    symbols: ["AAPL", "PETR4.SA", "BTC-USD"]
    interval: "60m"
    period: "1y"

sentiment:
  model_id: "ProsusAI/finbert"
  batch_size: 16

aggregation:
  window: "60min"          # bucket size
  decay_half_life: "6h"    # time‑decay for recency weighting

model:
  type: "logreg"
  horizon_bars: 1           # forward horizon in buckets
  calibration: "isotonic"  # better Brier score

signals:
  threshold_long: 0.62
  threshold_short: 0.38
  cooldown_minutes: 30
  costs_bps: 10

telegram:
  enabled: false
  token: ""
  chat_id: ""
```

Create `tickers.yml`:
```yaml
AAPL:
  aliases: ["Apple", "NASDAQ:AAPL", "AAPL"]
PETR4.SA:
  aliases: ["Petrobras", "PETR4", "B3:PETR4"]
BTC-USD:
  aliases: ["Bitcoin", "BTC", "BTCUSD"]
```

---

## 4) Step‑By‑Step Tasks (file‑by‑file)
Each task includes an **O3 Brief**, **Acceptance Criteria**, and **Constraints**.

### 4.1 Ingest — RSS client
**File:** `ingest/rss_client.py`

**O3 Brief:**
- Implement `fetch_rss(feeds: list[str], min_chars: int, allowed_langs: list[str]) -> pd.DataFrame`.
- Use `feedparser` to read feeds.
- Build rows with: `id (sha1 of title+source)`, `source (domain)`, `published_at (UTC ISO)`, `title`, `body (summary)`, `url`, `lang`.
- Detect language on `title + summary` via `langdetect`.
- Filter: drop rows with `len(title+body) < min_chars` or `lang not in allowed_langs`.
- Deduplicate by `id`.

**Acceptance Criteria:**
- Returns DataFrame with columns: `id, source, published_at, title, body, url, lang`.
- ≥ 200 articles from the provided feeds when run once.
- All timestamps are UTC ISO‑8601 strings.

**Constraints:**
- No global state. Pure function.
- Robust to feed timeouts (retry 2x, skip silently).

---

### 4.2 Ingest — Normalizer & Ticker mapping
**File:** `ingest/normalize.py`

**O3 Brief:**
- Implement `load_ticker_map(yaml_path) -> dict`.
- Implement `map_entities(df: pd.DataFrame, ticker_map: dict) -> pd.DataFrame`:
  - For each row, find tickers whose aliases appear (case‑insensitive) in `title` or `body`.
  - Add column `tickers: List[str]`.
  - Explode to **one row per (article, ticker)**.
  - Keep: `id, ticker, published_at, title, body, url, lang, source`.

**Acceptance Criteria:**
- Articles without any match are dropped.
- Exploded DataFrame has ≥ 100 rows for a typical run.

**Constraints:**
- Use compiled regex for each alias list.
- Preserve original `id`.

---

### 4.3 Sentiment — FinBERT inference (batched)
**File:** `sentiment/finbert.py`

**O3 Brief:**
- Class `FinBertSentiment(model_id: str, batch_size: int)`:
  - Load tokenizer & model from `transformers` (AutoTokenizer/AutoModelForSequenceClassification).
  - Auto‑select device (CUDA if available else CPU).
  - `predict_batch(texts: list[str]) -> pd.DataFrame` returning columns: `pos, neg, neu, score` where `score = pos - neg`.
  - Truncate texts to 256 tokens; handle empty/None safely (`neu=1.0, score=0.0`).

**Acceptance Criteria:**
- Batch inference on 1k texts completes without OOM.
- Output probabilities sum to 1 per row (±1e‑6).

**Constraints:**
- Deterministic (set seeds).
- No hardcoded model ids: read from args.

---

### 4.4 Features — Aggregate into time buckets
**File:** `features/aggregate.py`

**O3 Brief:**
- Implement `build_sentiment_bars(articles_csv: str, window: str, config_path: str) -> pd.DataFrame`:
  - Read `data/articles_raw.csv` (output of 4.2 after writing CSV in main).
  - For each row text = `title` + first 240 chars of `body`.
  - Run FinBERT in batches; get `score` and keep `uncertainty = neu`.
  - Floor `published_at` to bucket `window` per ticker → `bucket_start` (UTC, pandas period floor).
  - For each (ticker, bucket_start) compute:
    - `mean_sent, std_sent, min_sent, max_sent, count`.
    - `unc_mean` (mean of `uncertainty`).
    - `time_decay_mean` (exponential weights, half‑life from config).
  - Save to `data/sentiment_bars.csv`.

**Acceptance Criteria:**
- ≥ 1 week of hourly buckets present for at least one ticker.
- Latency: ≤ 1s per ticker per day of articles on CPU (rough guide).

**Constraints:**
- Use a single FinBERT instance per process.
- Vectorized aggregations; avoid Python loops over rows.

---

### 4.5 Labels — Align with prices & build dataset
**File:** `backtest/label.py`

**O3 Brief:**
- Implement `make_labels(sent_bars_csv: str, horizon_bars: int, price_cfg: dict) -> pd.DataFrame`:
  - Download OHLC with `yfinance` for each symbol in `price_cfg.symbols` using `interval` & `period` from config.
  - Resample/align closes to `bucket_start`.
  - Join with sentiment features on `(ticker, bucket_start)`.
  - Compute forward return `r_fwd = close[t+h]/close[t] - 1`.
  - Binary label `y = 1 if r_fwd > 0 else 0`.
  - Write `data/training_set.csv`.

**Acceptance Criteria:**
- No look‑ahead: label strictly uses future close.
- Rows with missing prices are dropped.

**Constraints:**
- Handle symbol mapping differences (e.g., PETR4 vs PETR4.SA).

---

### 4.6 Model — Calibrated probability
**File:** `models/prob_model.py`

**O3 Brief:**
- Class `ProbModel` wrapping `LogisticRegression` inside `CalibratedClassifierCV` (isotonic):
  - `fit(X: pd.DataFrame, y: pd.Series)` → trains and stores calibrator.
  - `predict_proba(X) -> np.ndarray` returns calibrated P(up).
  - `train_and_save(dataset_csv: str, model_path: str)` convenience.
  - `load(model_path: str) -> ProbModel`.
- Features: use regex select columns: `mean|std|min|max|count|unc|decay`.

**Acceptance Criteria:**
- Brier score < 0.20 on a simple train/val split (loose target for MVP).
- `predict_proba` stable on NaN‑filled inputs (NaNs → 0 with imputer).

**Constraints:**
- Seeded & deterministic.

---

### 4.7 Backtest — Event‑driven
**File:** `backtest/backtester.py`

**O3 Brief:**
- Implement `run(df: pd.DataFrame, model_path: str, threshold_long: float, costs_bps: int) -> dict`:
  - For each `(ticker, bucket_start)` sorted, compute `P(up)`.
  - Strategy: if `P > threshold_long`, **long for next 1 bucket**, PnL = forward return − costs.
  - Aggregate to equity curve; compute metrics: Total Return, Win Rate, Profit Factor, **Sharpe (daily resampled)**, Max Drawdown, AUC, Brier.
  - Save `outputs/equity.png` and `outputs/report.md`.

**Acceptance Criteria:**
- No data leakage (uses label horizon properly).
- Report includes calibration reliability plot (optional simple bin plot).

**Constraints:**
- Deterministic; no randomness beyond splits.

---

### 4.8 API — Minimal demo
**File:** `api/app.py`

**O3 Brief:**
- FastAPI with endpoints:
  - `POST /score_text` body `{text: str, ticker: str}` → run FinBERT on text and return `{prob_up, components}` where `prob_up` is from the trained model using current bar features recomputed from just this text (approx) or return raw `score` if dataset columns unavailable.
  - `GET /signal?ticker=XYZ` → load last row from `data/sentiment_bars.csv`, compute probability via model, return `{ticker, bucket_start, prob_up, decision}`.

**Acceptance Criteria:**
- `uvicorn api.app:app --reload` starts with no errors.
- cURL to `/score_text` returns JSON in < 500ms for small texts.

**Constraints:**
- Read‑only model. No training via API.

---

### 4.9 Telegram — Optional notifier
**File:** `notify/telegram.py`

**O3 Brief:**
- Implement `send_alert(token: str, chat_id: str, msg: str) -> None`.
- Script `notify_on_threshold.py`: read latest `sentiment_bars.csv`, compute `P(up)`, if `> threshold_long` send a formatted message with top 3 article titles & links from that bucket.

**Acceptance Criteria:**
- Works when `telegram.enabled=true` and env vars are present.

**Constraints:**
- Fail silently when disabled.

---

### 4.10 Orchestrator — One‑shot runner
**File:** `main.py`

**O3 Brief:**
- Steps:
  1) Load `config.yml` & `tickers.yml`.
  2) Ingest RSS → DataFrame → write `data/articles_raw.csv`.
  3) Aggregate with FinBERT → write `data/sentiment_bars.csv`.
  4) Label with prices → write `data/training_set.csv`.
  5) Train model → `outputs/prob_model.pkl`.
  6) Backtest → `outputs/report.md`, `outputs/equity.png`.
  7) Print summary: rows, training size, Brier, AUC, Sharpe, Total Return.
- Use `logging`, no prints; deterministic seeding.

**Acceptance Criteria:**
- Entire E2E runs in < 10 minutes on CPU.
- All artifacts saved to the paths listed above.

**Constraints:**
- Graceful failure if any stage returns empty data.

---

## 5) Quick‑Run Commands
```bash
# 1) Install deps
python -m pip install -r requirements.txt

# 2) One‑shot pipeline
python main.py

# 3) Start API (after a model exists)
uvicorn api.app:app --port 8000 --reload

# 4) Score a snippet
curl -X POST http://127.0.0.1:8000/score_text \
  -H "Content-Type: application/json" \
  -d '{"text":"Apple beats earnings; guidance strong.","ticker":"AAPL"}'
```

---

## 6) Testing & DoD (Definition of Done)
**Sanity checks:**
- Ingest: `data/articles_raw.csv` has ≥ 500 rows, languages in {en, pt}.
- Sentiment: FinBERT outputs `pos+neg+neu≈1.0`; distribution not degenerate.
- Aggregation: `sentiment_bars.csv` has per‑ticker hourly buckets with `count>0`.
- Labels: No look‑ahead; missing price rows dropped.
- Model: `Brier < 0.20` on holdout; probability histogram is not all near 0.5.
- Backtest: Report exists; metrics computed; equity.png non‑empty image.
- API: `/score_text` returns quickly; `/signal` returns last prob & decision.

**Quality gates:**
- Determinism (fixed seeds).
- Config‑driven (no magic numbers).
- Error handling with clear logs.
- No heavy loops over rows (use vectorization).

---

## 7) Parallel to AXON — Hand‑off
- Do **not** change AXON.
- If needed, export `data/sentiment_bars.csv` to an AXON‑readable location; AXON can ingest it as an external feature file later.
- Keep this repo separate so we can iterate independently.

---

## 8) Troubleshooting
- **Torch install fails (Windows CPU):** install official CPU wheel; avoid CUDA if no GPU.
- **Low coverage of articles:** add more RSS feeds; reduce `min_chars` to 80; run multiple times per day.
- **Class imbalance:** keep calibration (isotonic) and monitor Brier score; adjust thresholds.
- **Latency too high:** increase `batch_size` to 32; truncate texts to first 200–256 tokens.

---

## 9) Stretch (optional, if time permits)
- Add Loughran–McDonald lexicon as a secondary signal, then blend with FinBERT.
- Add simple novelty/source‑quality weights.
- Export SHAP on the logistic model for basic interpretability.
- Add `/health` endpoint & minimal Streamlit dashboard.

---

## 10) Ready‑To‑Use O3 Prompts (copy/paste)

**A) `ingest/rss_client.py`**
```
Implement fetch_rss(feeds: list[str], min_chars: int, allowed_langs: list[str]) -> pd.DataFrame using feedparser and langdetect.
Return columns [id, source, published_at, title, body, url, lang].
Compute id = sha1((title or "") + (parsed.feed.link or domain)).
Ensure published_at is UTC ISO string; retry network errors up to 2 times.
Deduplicate by id. Filter by min_chars and allowed_langs.
```

**B) `ingest/normalize.py`**
```
Implement load_ticker_map(yaml_path) -> dict and map_entities(df, ticker_map) -> pd.DataFrame.
Case-insensitive alias matching on title/body via compiled regex per ticker.
Add column tickers: List[str]; explode to one row per (article, ticker).
Keep columns [id, ticker, published_at, title, body, url, lang, source]. Drop rows with no tickers.
```

**C) `sentiment/finbert.py`**
```
Create class FinBertSentiment(model_id: str, batch_size: int=16).
Load AutoTokenizer and AutoModelForSequenceClassification from transformers.
Auto-select device (cuda if available else cpu).
Method predict_batch(texts: list[str]) -> pd.DataFrame returns columns [pos, neg, neu, score] with score = pos - neg.
Truncate to 256 tokens; handle empty text by returning neu=1.0.
```

**D) `features/aggregate.py`**
```
Implement build_sentiment_bars(articles_csv, window, config_path) -> pd.DataFrame.
Load config (model_id, batch_size, half-life). Build one FinBERT instance.
Concatenate title + first 240 body chars; batch through FinBERT.
Floor published_at to the bucket window per ticker as bucket_start (UTC).
Aggregate features per (ticker, bucket_start): mean_sent, std_sent, min_sent, max_sent, count, unc_mean=neu_mean, time_decay_mean (exponential weights).
Save to data/sentiment_bars.csv and return it.
```

**E) `backtest/label.py`**
```
Implement make_labels(sent_bars_csv: str, horizon_bars: int, price_cfg: dict) -> pd.DataFrame.
Download OHLC via yfinance for each symbol (period, interval).
Align closes to bucket_start; compute r_fwd = close[t+h]/close[t] - 1; label y = 1 if r_fwd>0 else 0.
Write data/training_set.csv and return the merged DataFrame.
```

**F) `models/prob_model.py`**
```
Implement class ProbModel using LogisticRegression wrapped by CalibratedClassifierCV(method='isotonic').
Provide fit, predict_proba, train_and_save(dataset_csv, model_path), and load(model_path).
Use only columns matching (mean|std|min|max|count|unc|decay). Fill NaNs with 0. Set seeds for determinism.
```

**G) `backtest/backtester.py`**
```
Implement run(df, model_path, threshold_long, costs_bps) -> dict.
Load model; compute P(up) for each row sorted by ticker, bucket_start.
If P>threshold_long, long for next bucket: pnl = r_fwd - costs_bps*1e-4.
Aggregate to equity; compute Total Return, Win Rate, Profit Factor, Sharpe (daily), Max Drawdown, AUC, Brier.
Save equity.png and report.md under outputs/. Return metrics dict.
```

**H) `api/app.py`**
```
Create FastAPI with POST /score_text {text, ticker} and GET /signal?ticker=XYZ.
Use outputs/prob_model.pkl if present; otherwise return raw FinBERT score.
Read last row of data/sentiment_bars.csv for GET /signal.
Return JSON with ticker, bucket_start, prob_up, decision.
```

**I) `notify/telegram.py`**
```
Implement send_alert(token, chat_id, msg). Provide script notify_on_threshold.py reading the latest buckets, computing prob, and sending alerts when prob exceeds threshold.
```

**J) `main.py`**
```
Implement an end-to-end runner: load configs, ingest RSS, normalize/map, write data/articles_raw.csv; aggregate FinBERT scores into data/sentiment_bars.csv; build labels with prices; train and save calibrated model; run backtest and save outputs/report.md and outputs/equity.png; log key metrics.
```

---

## 11) What to show in the demo (3 minutes)
1) `python main.py` → show outputs generated.
2) `uvicorn api.app:app --reload` → cURL `/score_text` and `/signal`.
3) Open `outputs/report.md` and `outputs/equity.png`.
4) (Optional) Trigger Telegram notifier with a high‑probability bucket.

---

**End of Guide** ✅

