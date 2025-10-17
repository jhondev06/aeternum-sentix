from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import pandas as pd
import yaml
from sentiment.finbert import FinBertSentiment
from models.prob_model import ProbModel
from alerts.engine import AlertEngine
from alerts.rule import AlertRule
from alerts.webhook import WebhookConfig
import os
import secrets

app = FastAPI()
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Load config
with open('config.yml', 'r') as f:
    config = yaml.safe_load(f)

model_id = config['sentiment']['model_id']
batch_size = config['sentiment']['batch_size']
device = config['sentiment'].get('device')
threshold_long = config['signals']['threshold_long']
api_username = config['api']['auth']['username']
api_password = config['api']['auth']['password']

security = HTTPBasic()

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, api_username)
    correct_password = secrets.compare_digest(credentials.password, api_password)
    if not (correct_username and correct_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    return credentials.username

# Load FinBERT
finbert = FinBertSentiment(model_id, batch_size, device)

# Load model if exists
model = None
if os.path.exists('outputs/prob_model.pkl'):
    model = ProbModel.load('outputs/prob_model.pkl')

# Initialize alert engine
alert_engine = AlertEngine()
if config.get('alerts', {}).get('enabled', False):
    alert_engine.start_monitoring(config['alerts'].get('monitoring_interval', 60))

class ScoreTextRequest(BaseModel):
    text: str
    ticker: str

class AlertRuleRequest(BaseModel):
    rule_id: str
    name: str
    ticker: str
    conditions: List[Dict]
    actions: List[Dict]
    enabled: bool = True
    cooldown_minutes: int = 30

class WebhookRequest(BaseModel):
    url: str
    headers: Optional[Dict] = None
    enabled: bool = True

@app.post("/score_text")
def score_text(request: ScoreTextRequest, username: str = Depends(authenticate)):
    text = request.text
    if not text.strip():
        return {"prob_up": 0.5, "components": {"pos": 0, "neg": 0, "neu": 1, "score": 0}}

    sentiment = finbert.predict_batch([text]).iloc[0]
    pos, neg, neu, score = sentiment['pos'], sentiment['neg'], sentiment['neu'], sentiment['score']

    if model:
        # Approximate features: use score as mean_sent, etc.
        dummy_features = pd.DataFrame({
            'mean_sent': [score],
            'std_sent': [0],
            'min_sent': [score],
            'max_sent': [score],
            'count': [1],
            'unc_mean': [neu],
            'time_decay_mean': [score]
        })
        prob_up = model.predict_proba(dummy_features)[0]
    else:
        prob_up = (score + 1) / 2  # normalize to 0-1

    return {
        "prob_up": float(prob_up),
        "components": {
            "pos": float(pos),
            "neg": float(neg),
            "neu": float(neu),
            "score": float(score)
        }
    }

@app.get("/signal")
def get_signal(ticker: str, threshold_long: float = None, threshold_short: float = None, username: str = Depends(authenticate)):
    if threshold_long is None:
        threshold_long = config['signals']['threshold_long']
    if threshold_short is None:
        threshold_short = config['signals']['threshold_short']

    if not os.path.exists('data/sentiment_bars.csv'):
        raise HTTPException(status_code=404, detail="Sentiment bars not found")

    df = pd.read_csv('data/sentiment_bars.csv')
    df['bucket_start'] = pd.to_datetime(df['bucket_start'])
    last_row = df[df['ticker'] == ticker].sort_values('bucket_start').iloc[-1] if not df[df['ticker'] == ticker].empty else None

    if last_row is None:
        raise HTTPException(status_code=404, detail=f"No data for ticker {ticker}")

    if model:
        features = last_row.to_frame().T
        if getattr(model, 'feature_cols', None):
            features = features.reindex(columns=model.feature_cols, fill_value=0)
        prob_up = model.predict_proba(features)[0]
    else:
        prob_up = 0.5  # default

    if prob_up > threshold_long:
        decision = "long"
    elif prob_up < threshold_short:
        decision = "short"
    else:
        decision = "hold"

    return {
        "ticker": ticker,
        "bucket_start": last_row['bucket_start'].isoformat(),
        "prob_up": float(prob_up),
        "decision": decision,
        "thresholds": {"long": threshold_long, "short": threshold_short}
    }


@app.get("/probabilities")
def get_probabilities(ticker: str, username: str = Depends(authenticate)):
    """Consultar probabilidades quantificadas de subir/descer para um ticker."""
    if not os.path.exists('data/sentiment_bars.csv'):
        raise HTTPException(status_code=404, detail="Sentiment bars not found")

    df = pd.read_csv('data/sentiment_bars.csv')
    df['bucket_start'] = pd.to_datetime(df['bucket_start'])

    df_ticker = df[df['ticker'] == ticker]
    if df_ticker.empty:
        raise HTTPException(status_code=404, detail=f"No data for ticker {ticker}")

    last_row = df_ticker.sort_values('bucket_start').iloc[-1]
    features_df = last_row.to_frame().T

    if model:
        if getattr(model, 'feature_cols', None):
            features_df = features_df.reindex(columns=model.feature_cols, fill_value=0)
        prob_up = float(model.predict_proba(features_df)[0])
    else:
        prob_up = 0.5

    prob_down = 1.0 - prob_up

    components = {
        "mean_sent": float(last_row['mean_sent']),
        "std_sent": float(last_row['std_sent']) if pd.notna(last_row['std_sent']) else None,
        "min_sent": float(last_row['min_sent']),
        "max_sent": float(last_row['max_sent']),
        "count": int(last_row['count']),
        "unc_mean": float(last_row['unc_mean']),
        "time_decay_mean": float(last_row['time_decay_mean'])
    }

    # Features efetivamente passadas ao modelo (com zeros onde faltar)
    model_features = {}
    try:
        if model and getattr(model, 'feature_cols', None):
            for col in model.feature_cols:
                model_features[col] = float(features_df[col].iloc[0]) if col in features_df.columns else 0.0
        else:
            # Fallback: usar as principais features do arquivo
            for col in ["mean_sent", "std_sent", "min_sent", "max_sent", "count", "unc_mean", "time_decay_mean"]:
                if col in features_df.columns:
                    model_features[col] = float(features_df[col].iloc[0])
    except Exception:
        model_features = {}

    return {
        "ticker": ticker,
        "bucket_start": last_row['bucket_start'].isoformat(),
        "prob_up": prob_up,
        "prob_down": prob_down,
        "components": components,
        "model_features": model_features
    }

@app.get("/realtime")
def get_realtime(ticker: str = None, username: str = Depends(authenticate)):
    if not os.path.exists('data/sentiment_bars.csv'):
        raise HTTPException(status_code=404, detail="Sentiment bars not found")

    df = pd.read_csv('data/sentiment_bars.csv')
    df['bucket_start'] = pd.to_datetime(df['bucket_start'])

    if ticker:
        df = df[df['ticker'] == ticker]

    # Get latest for each ticker
    latest = df.sort_values('bucket_start').groupby('ticker').last().reset_index()

    result = []
    for _, row in latest.iterrows():
        result.append({
            "ticker": row['ticker'],
            "bucket_start": row['bucket_start'].isoformat(),
            "mean_sent": float(row['mean_sent']),
            "std_sent": float(row['std_sent']) if pd.notna(row['std_sent']) else None,
            "min_sent": float(row['min_sent']),
            "max_sent": float(row['max_sent']),
            "count": int(row['count']),
            "unc_mean": float(row['unc_mean']),
            "time_decay_mean": float(row['time_decay_mean'])
        })

    return {"data": result}

@app.get("/historical")
def get_historical(ticker: str = None, start_date: str = None, end_date: str = None, username: str = Depends(authenticate)):
    if not os.path.exists('data/sentiment_bars.csv'):
        raise HTTPException(status_code=404, detail="Sentiment bars not found")

    df = pd.read_csv('data/sentiment_bars.csv')
    df['bucket_start'] = pd.to_datetime(df['bucket_start'])

    if ticker:
        df = df[df['ticker'] == ticker]

    if start_date:
        start = pd.to_datetime(start_date)
        df = df[df['bucket_start'] >= start]

    if end_date:
        end = pd.to_datetime(end_date)
        df = df[df['bucket_start'] <= end]

    df = df.sort_values('bucket_start')

    result = []
    for _, row in df.iterrows():
        result.append({
            "ticker": row['ticker'],
            "bucket_start": row['bucket_start'].isoformat(),
            "mean_sent": float(row['mean_sent']),
            "std_sent": float(row['std_sent']) if pd.notna(row['std_sent']) else None,
            "min_sent": float(row['min_sent']),
            "max_sent": float(row['max_sent']),
            "count": int(row['count']),
            "unc_mean": float(row['unc_mean']),
            "time_decay_mean": float(row['time_decay_mean'])
        })

    return {"data": result, "count": len(result)}

# Alert Management Endpoints

@app.post("/alerts/rules")
def create_alert_rule(request: AlertRuleRequest, username: str = Depends(authenticate)):
    """Create a new alert rule"""
    try:
        rule = AlertRule(
            rule_id=request.rule_id,
            name=request.name,
            ticker=request.ticker,
            conditions=request.conditions,
            actions=request.actions,
            enabled=request.enabled,
            cooldown_minutes=request.cooldown_minutes
        )
        alert_engine.add_rule(rule)
        return {"message": "Alert rule created successfully", "rule_id": request.rule_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating alert rule: {str(e)}")

@app.get("/alerts/rules")
def list_alert_rules(username: str = Depends(authenticate)):
    """List all alert rules"""
    return {"rules": alert_engine.list_rules()}

@app.get("/alerts/rules/{rule_id}")
def get_alert_rule(rule_id: str, username: str = Depends(authenticate)):
    """Get a specific alert rule"""
    rule = alert_engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return rule.to_dict()

@app.put("/alerts/rules/{rule_id}")
def update_alert_rule(rule_id: str, request: AlertRuleRequest, username: str = Depends(authenticate)):
    """Update an alert rule"""
    try:
        rule = AlertRule(
            rule_id=rule_id,
            name=request.name,
            ticker=request.ticker,
            conditions=request.conditions,
            actions=request.actions,
            enabled=request.enabled,
            cooldown_minutes=request.cooldown_minutes
        )
        alert_engine.add_rule(rule)
        return {"message": "Alert rule updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error updating alert rule: {str(e)}")

@app.delete("/alerts/rules/{rule_id}")
def delete_alert_rule(rule_id: str, username: str = Depends(authenticate)):
    """Delete an alert rule"""
    if alert_engine.remove_rule(rule_id):
        return {"message": "Alert rule deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Alert rule not found")

# Webhook Management Endpoints

@app.post("/alerts/webhooks")
def create_webhook(request: WebhookRequest, username: str = Depends(authenticate)):
    """Create a new webhook configuration"""
    try:
        webhook = WebhookConfig(
            url=request.url,
            headers=request.headers,
            enabled=request.enabled
        )
        alert_engine.add_webhook(webhook)
        return {"message": "Webhook created successfully", "url": request.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating webhook: {str(e)}")

@app.get("/alerts/webhooks")
def list_webhooks(username: str = Depends(authenticate)):
    """List all webhook configurations"""
    return {"webhooks": alert_engine.list_webhooks()}

@app.delete("/alerts/webhooks/{webhook_url:path}")
def delete_webhook(webhook_url: str, username: str = Depends(authenticate)):
    """Delete a webhook configuration"""
    if alert_engine.remove_webhook(webhook_url):
        return {"message": "Webhook deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Webhook not found")

# Alert Monitoring Endpoints

@app.post("/alerts/process")
def process_alerts(username: str = Depends(authenticate)):
    """Manually process alerts (for testing)"""
    if not os.path.exists('data/sentiment_bars.csv'):
        raise HTTPException(status_code=404, detail="Sentiment bars not found")

    df = pd.read_csv('data/sentiment_bars.csv')
    df['bucket_start'] = pd.to_datetime(df['bucket_start'])

    triggered_alerts = alert_engine.process_alerts(df)
    if triggered_alerts:
        alert_engine.execute_actions(triggered_alerts)

    return {
        "message": f"Processed {len(triggered_alerts)} alerts",
        "triggered_rules": [alert['rule'].rule_id for alert in triggered_alerts]
    }

@app.get("/alerts/stats")
def get_alert_stats(username: str = Depends(authenticate)):
    """Get alert system statistics"""
    return alert_engine.get_stats()

@app.get("/health")
def health_check():
    """Health check endpoint for cloud deployment"""
    return {"status": "healthy", "version": "1.0.0"}
@app.get("/alerts/history")
def get_alert_history(rule_id: str = None, days: int = 7, username: str = Depends(authenticate)):
    """Get alert history"""
    df = alert_engine.logger.get_alert_history(rule_id, days)
    return {
        "history": df.to_dict('records') if not df.empty else [],
        "count": len(df)
    }