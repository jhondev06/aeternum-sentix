# Custom Alerts System (External Webhooks)

This module provides a comprehensive alerts system for real-time trading signals based on sentiment analysis data.

## Features

- **Programmable Alerts**: Create custom rules with conditional logic
- **Dynamic Thresholds**: Support for various comparison operators and value ranges
- **Real-time Webhooks**: Send alerts to external systems instantly
- **Conditional Rules**: Combine multiple conditions (e.g., sentiment + volatility)
- **API Configuration**: Full REST API for rule and webhook management
- **Comprehensive Logging**: Track all alert triggers and deliveries
- **Background Monitoring**: Continuous processing of sentiment data

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Alert Rules   │    │  Alert Engine   │    │   Webhook Mgr   │
│                 │    │                 │    │                 │
│ - Conditions    │───▶│ - Process Rules │───▶│ - Send Signals  │
│ - Actions       │    │ - Trigger Alerts│    │ - Handle Retry  │
│ - Thresholds    │    │ - Execute Actions│    │ - Async Support │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Alert Logger  │
                       │                 │
                       │ - Log Triggers │
                       │ - Track Delivery│
                       │ - Generate Stats│
                       └─────────────────┘
```

## Quick Start

### 1. Basic Usage

```python
from alerts.engine import AlertEngine
from alerts.rule import AlertRule

# Initialize engine
engine = AlertEngine()

# Create a rule
rule = AlertRule(
    rule_id="test_rule",
    name="Test Alert",
    ticker="PETR4.SA",
    conditions=[
        {"field": "mean_sent", "operator": ">", "value": 0.6}
    ],
    actions=[
        {"type": "webhook", "url": "https://your-webhook-endpoint.com/signal"}
    ]
)

# Add rule and start monitoring
engine.add_rule(rule)
engine.start_monitoring()
```

### 2. API Usage

```bash
# Create a rule
curl -X POST "http://localhost:8000/alerts/rules" \
  -H "Content-Type: application/json" \
  -u "admin:sentix123" \
  -d '{
    "rule_id": "ipca_alert",
    "name": "IPCA Sentiment Alert",
    "ticker": "IPCA",
    "conditions": [
      {"field": "mean_sent", "operator": ">", "value": 0.7}
    ],
    "actions": [
      {"type": "webhook", "url": "https://your-webhook-endpoint.com/webhook"}
    ]
  }'

# List all rules
curl -X GET "http://localhost:8000/alerts/rules" -u "admin:sentix123"

# Process alerts manually
curl -X POST "http://localhost:8000/alerts/process" -u "admin:sentix123"
```

## Rule Conditions

### Supported Fields
- `mean_sent`: Mean sentiment score
- `std_sent`: Sentiment standard deviation
- `min_sent`: Minimum sentiment score
- `max_sent`: Maximum sentiment score
- `count`: Number of articles
- `unc_mean`: Mean uncertainty
- `time_decay_mean`: Time-decayed mean sentiment
- `volatility`: Price/market volatility (external data)

### Supported Operators
- `>` : Greater than
- `<` : Less than
- `>=` : Greater than or equal
- `<=` : Less than or equal
- `==` : Equal
- `!=` : Not equal
- `between` : Value between range [min, max]
- `outside` : Value outside range [min, max]
- `cross_above` : Crossed above threshold
- `cross_below` : Crossed below threshold

### Example Conditions

```python
# Single condition
{"field": "mean_sent", "operator": ">", "value": 0.6}

# Range condition
{"field": "std_sent", "operator": "between", "value": [0.2, 0.8]}

# Multiple conditions (AND logic)
conditions = [
    {"field": "mean_sent", "operator": ">", "value": 0.7},
    {"field": "volatility", "operator": ">", "value": 0.8}
]
```

## Actions

### Webhook Action
```python
{
    "type": "webhook",
    "url": "https://your-hft-system.com/signals",
    "signal_type": "long_signal",
    "message": "Custom message"
}
```

### Telegram Action
```python
{
    "type": "telegram",
    "message": "🚨 Alert message"
}
```

### Log Action
```python
{
    "type": "log"  # Automatically logged
}
```

## Webhook Payload

When an alert triggers, the following payload is sent:

```json
{
    "timestamp": "2025-01-11T23:01:03.253Z",
    "type": "trading_signal",
    "signal": {
        "rule_id": "ipca_volatility_alert",
        "rule_name": "IPCA High Sentiment + High Volatility",
        "ticker": "IPCA",
        "signal_type": "long_signal",
        "message": "IPCA sentiment bullish with high volatility",
        "timestamp": "2025-01-11T23:01:03.253Z"
    }
}
```

## Configuration

Add to your `config.yml`:

```yaml
alerts:
  enabled: true
  monitoring_interval: 60  # seconds
  max_concurrent_webhooks: 10
  webhook_timeout: 10  # seconds
  log_retention_days: 30
  default_cooldown_minutes: 30
```

## API Endpoints

### Alert Rules
- `POST /alerts/rules` - Create rule
- `GET /alerts/rules` - List rules
- `GET /alerts/rules/{rule_id}` - Get rule
- `PUT /alerts/rules/{rule_id}` - Update rule
- `DELETE /alerts/rules/{rule_id}` - Delete rule

### Webhooks
- `POST /alerts/webhooks` - Create webhook
- `GET /alerts/webhooks` - List webhooks
- `DELETE /alerts/webhooks/{url}` - Delete webhook

### Monitoring
- `POST /alerts/process` - Process alerts manually
- `GET /alerts/stats` - Get system statistics
- `GET /alerts/history` - Get alert history

## Logging

Logs are stored in `logs/alerts/` with daily rotation:
- Alert triggers
- Webhook delivery status
- Telegram delivery status
- System errors

## Example Use Cases

### 1. Sentiment + Volatility Alert
```python
rule = AlertRule(
    rule_id="sent_vol_alert",
    name="High Sentiment + High Volatility",
    ticker="PETR4.SA",
    conditions=[
        {"field": "mean_sent", "operator": ">", "value": 0.7},
        {"field": "volatility", "operator": ">", "value": 0.8}
    ],
    actions=[{"type": "webhook", "url": "https://hft.com/signal"}]
)
```

### 2. Extreme Sentiment Movement
```python
rule = AlertRule(
    rule_id="extreme_sent",
    name="Extreme Sentiment Volatility",
    ticker="VALE3.SA",
    conditions=[
        {"field": "std_sent", "operator": ">", "value": 0.5},
        {"field": "count", "operator": ">", "value": 20}
    ],
    actions=[{"type": "telegram", "message": "Extreme volatility detected"}]
)
```

### 3. Multi-Asset Alert
Create similar rules for different tickers and combine them with your external monitoring or analytics strategy.

## External Integration via Webhooks

### Using a Local Webhook Receiver

For local testing, you can use a simple webhook receiver (Flask/Node) to accept POST notifications from Sentix alerts.

#### 1. Start a Local Webhook Receiver

```bash
# Start a simple local webhook receiver (Flask example)
pip install flask
python -c "from flask import Flask, request; app=Flask(__name__);\n@app.post('/hook')\ndef hook(): print('Alert:', request.json); return {'ok': True}\napp.run(port=8080)"
```

Your local receiver will typically expose `http://localhost:8080` endpoints such as:
- `POST /hook` - Receive alerts
- `GET /health` - Health check

#### 2. Configure Webhook for External Integration

```bash
# Create webhook configuration
curl -X POST "http://localhost:8000/alerts/webhooks" \
  -H "Content-Type: application/json" \
  -u "admin:sentix123" \
  -d '{
    "url": "http://localhost:8080/hook",
    "enabled": true
  }'
```

#### 3. Create Alert Rules for Trading Signals

```bash
# Long signal rule
curl -X POST "http://localhost:8000/alerts/rules" \
  -H "Content-Type: application/json" \
  -u "admin:sentix123" \
  -d '{
    "rule_id": "petr_long_signal",
    "name": "PETR4 Long Signal",
    "ticker": "PETR4.SA",
    "conditions": [
      {"field": "mean_sent", "operator": ">", "value": 0.6}
    ],
    "actions": [
      {
        "type": "webhook",
        "url": "http://localhost:8080/hook",
        "signal_type": "long_signal"
      }
    ],
    "enabled": true,
    "cooldown_minutes": 30
  }'

# Short signal rule
curl -X POST "http://localhost:8000/alerts/rules" \
  -H "Content-Type: application/json" \
  -u "admin:sentix123" \
  -d '{
    "rule_id": "petr_short_signal",
    "name": "PETR4 Short Signal",
    "ticker": "PETR4.SA",
    "conditions": [
      {"field": "mean_sent", "operator": "<", "value": -0.4}
    ],
    "actions": [
      {
        "type": "webhook",
        "url": "http://localhost:8080/hook",
        "signal_type": "short_signal"
      }
    ],
    "enabled": true,
    "cooldown_minutes": 30
  }'
```

#### 4. Monitor the Local Receiver

```bash
# Check health (if implemented)
curl http://localhost:8080/health
```

#### 5. View Alert History

```bash
# Get recent alerts
curl -X GET "http://localhost:8000/alerts/history" -u "admin:sentix123"

# Get alerts for specific rule
curl -X GET "http://localhost:8000/alerts/history?rule_id=petr_long_signal" -u "admin:sentix123"
```

### Integration with External Systems (Production)

1. **Configure Webhooks**: Set up webhook URLs in your external system
2. **Create Rules**: Define alert conditions based on your strategy
3. **Monitor**: Use the API to track alert performance
4. **Adjust**: Modify thresholds based on backtesting results

### Signal Payload Format

The webhook sends the following payload to your external system:

```json
{
  "timestamp": "2025-01-11T23:01:03.253Z",
  "type": "trading_signal",
  "signal": {
    "rule_id": "petr_long_signal",
    "rule_name": "PETR4 Long Signal",
    "ticker": "PETR4.SA",
    "signal_type": "long",
    "message": "Alert triggered for PETR4.SA",
    "timestamp": "2025-01-11T23:01:03.253Z"
  }
}
```

Your external system should parse the `signal` object and trigger the appropriate action (notifications, logging, downstream processing).

## Best Practices

1. **Cooldown Periods**: Set appropriate cooldown to avoid spam
2. **Threshold Calibration**: Test thresholds with historical data
3. **Error Handling**: Monitor webhook delivery logs
4. **Rate Limiting**: Consider rate limits and throughput for your external system or webhook receiver
5. **Backup Channels**: Use both webhooks and telegram for critical alerts

## Troubleshooting

- Check `logs/alerts/` for detailed logs
- Use `/alerts/stats` endpoint for system health
- Use `/alerts/process` for manual testing
- Verify webhook URLs are accessible
- Check authentication credentials