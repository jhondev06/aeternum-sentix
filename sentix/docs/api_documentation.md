# Sentix API Documentation

## Overview

The Sentix API provides programmatic access to sentiment analysis capabilities, trading signals, and alert management. Built with FastAPI, it offers RESTful endpoints for real-time and historical data access.

## Authentication

All API endpoints require HTTP Basic Authentication.

**Credentials** (configured in `config.yml`):
- Username: `admin`
- Password: `sentix123`

**Example using curl**:
```bash
curl -u admin:sentix123 http://localhost:8000/signal?ticker=PETR4.SA
```

## Base URL

```
http://localhost:8000
```

## Endpoints

### Sentiment Analysis

#### POST /score_text

Analyze sentiment of a text snippet and return probability of price increase.

**Request Body**:
```json
{
  "text": "Apple supera expectativas; guidance forte.",
  "ticker": "AAPL"
}
```

**Response**:
```json
{
  "prob_up": 0.75,
  "components": {
    "pos": 0.8,
    "neg": 0.1,
    "neu": 0.1,
    "score": 0.7
  }
}
```

**Parameters**:
- `text`: Text to analyze (string, required)
- `ticker`: Associated ticker symbol (string, required)

**Response Fields**:
- `prob_up`: Probability of price increase (0-1)
- `components.pos`: Positive sentiment score
- `components.neg`: Negative sentiment score
- `components.neu`: Neutral sentiment score
- `components.score`: Overall sentiment score (-1 to 1)

#### GET /signal

Get trading signal for a specific ticker.

**Query Parameters**:
- `ticker`: Ticker symbol (required)
- `threshold_long`: Long threshold (optional, default: 0.62)
- `threshold_short`: Short threshold (optional, default: 0.38)

**Response**:
```json
{
  "ticker": "PETR4.SA",
  "bucket_start": "2024-01-15T00:00:00",
  "prob_up": 0.68,
  "decision": "long",
  "thresholds": {
    "long": 0.62,
    "short": 0.38
  }
}
```

**Decision Logic**:
- `long`: prob_up > threshold_long
- `short`: prob_up < threshold_short
- `hold`: otherwise

### Data Access

#### GET /realtime

Fetch latest sentiment data for all tickers or a specific ticker.

**Query Parameters**:
- `ticker`: Filter by specific ticker (optional)

**Response**:
```json
{
  "data": [
    {
      "ticker": "PETR4.SA",
      "bucket_start": "2024-01-15T00:00:00",
      "mean_sent": 0.15,
      "std_sent": 0.25,
      "min_sent": -0.3,
      "max_sent": 0.8,
      "count": 45,
      "unc_mean": 0.4,
      "time_decay_mean": 0.12
    }
  ]
}
```

#### GET /historical

Query historical sentiment data with date filtering.

**Query Parameters**:
- `ticker`: Filter by specific ticker (optional)
- `start_date`: Start date (ISO format, optional)
- `end_date`: End date (ISO format, optional)

**Response**:
```json
{
  "data": [...],
  "count": 52
}
```

### Alert Management

#### POST /alerts/rules

Create a new alert rule.

**Request Body**:
```json
{
  "rule_id": "petr_high_sentiment",
  "name": "PETR4 High Sentiment Alert",
  "ticker": "PETR4.SA",
  "conditions": [
    {
      "field": "mean_sent",
      "operator": ">",
      "value": 0.5
    }
  ],
  "actions": [
    {
      "type": "webhook",
      "url": "https://example.com/webhook"
    }
  ],
  "enabled": true,
  "cooldown_minutes": 30
}
```

**Response**:
```json
{
  "message": "Alert rule created successfully",
  "rule_id": "petr_high_sentiment"
}
```

#### GET /alerts/rules

List all alert rules.

**Response**:
```json
{
  "rules": [
    {
      "rule_id": "petr_high_sentiment",
      "name": "PETR4 High Sentiment Alert",
      "ticker": "PETR4.SA",
      "enabled": true,
      "cooldown_minutes": 30
    }
  ]
}
```

#### GET /alerts/rules/{rule_id}

Get details of a specific alert rule.

**Response**: Full rule configuration object.

#### PUT /alerts/rules/{rule_id}

Update an existing alert rule.

**Request Body**: Same as POST /alerts/rules

#### DELETE /alerts/rules/{rule_id}

Delete an alert rule.

**Response**:
```json
{
  "message": "Alert rule deleted successfully"
}
```

### Webhook Management

#### POST /alerts/webhooks

Create a webhook configuration for alert notifications.

**Request Body**:
```json
{
  "url": "https://example.com/alert-webhook",
  "headers": {
    "Authorization": "Bearer token123",
    "Content-Type": "application/json"
  },
  "enabled": true
}
```

#### GET /alerts/webhooks

List all webhook configurations.

#### DELETE /alerts/webhooks/{webhook_url}

Delete a webhook configuration.

### Alert Monitoring

#### POST /alerts/process

Manually trigger alert processing (for testing).

**Response**:
```json
{
  "message": "Processed 2 alerts",
  "triggered_rules": ["petr_high_sentiment", "vale_low_sentiment"]
}
```

#### GET /alerts/stats

Get alert system statistics.

**Response**:
```json
{
  "total_rules": 5,
  "active_rules": 3,
  "total_alerts_triggered": 127,
  "alerts_last_24h": 8
}
```

#### GET /alerts/history

Get alert execution history.

**Query Parameters**:
- `rule_id`: Filter by specific rule (optional)
- `days`: Number of days to look back (default: 7)

**Response**:
```json
{
  "history": [
    {
      "timestamp": "2024-01-15T14:30:00",
      "rule_id": "petr_high_sentiment",
      "ticker": "PETR4.SA",
      "trigger_value": 0.65,
      "actions_executed": ["webhook"]
    }
  ],
  "count": 15
}
```

## Error Handling

All endpoints return standard HTTP status codes:

- `200`: Success
- `400`: Bad Request (invalid parameters)
- `401`: Unauthorized (authentication failed)
- `404`: Not Found (resource doesn't exist)
- `500`: Internal Server Error

Error responses include a `detail` field with error description:

```json
{
  "detail": "Incorrect username or password"
}
```

## Rate Limiting

- No explicit rate limiting implemented
- Consider implementing based on usage patterns
- Monitor API usage through logs

## Data Formats

- **Dates**: ISO 8601 format (e.g., "2024-01-15T14:30:00")
- **Numbers**: Float with appropriate precision
- **Booleans**: Standard JSON boolean values

## Best Practices

1. **Authentication**: Always include credentials in requests
2. **Error Handling**: Check HTTP status codes and handle errors gracefully
3. **Caching**: Cache responses when appropriate to reduce API calls
4. **Monitoring**: Monitor API usage and performance
5. **Testing**: Use the `/alerts/process` endpoint for testing alert rules

## SDKs and Libraries

Currently, no official SDKs are available. Use standard HTTP libraries:

- Python: `requests` library
- JavaScript: `fetch` API or `axios`
- curl: Command-line tool for testing

## Integração com sistemas externos (Webhooks)

O Sentix pode enviar notificações e eventos para sistemas externos (monitoramento/analytics) via webhooks.

### Configuração Básica

1. **Iniciar serviços**:
   ```bash
   # API Sentix
   cd sentix && uvicorn api.app:app --host 0.0.0.0 --port 8000

   # Dashboard (opcional)
   streamlit run sentix/dashboard.py
   ```

2. **Configurar webhook**:
   ```bash
   curl -X POST "http://localhost:8000/alerts/webhooks" \
     -H "Content-Type: application/json" \
     -u "admin:sentix123" \
     -d '{"url": "https://your-webhook-endpoint.com/alerts", "enabled": true}'
   ```

3. **Criar regra de alerta**:
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

4. **Testar processamento manual**:
   ```bash
   curl -X POST "http://localhost:8000/alerts/process" -u "admin:sentix123"
   ```

### Payload de exemplo

```json
{
  "timestamp": "2025-01-11T23:01:03.253Z",
  "type": "alert",
  "signal": {
    "ticker": "PETR4.SA",
    "signal_type": "long",
    "rule_name": "Alerta Sentimento PETR4",
    "timestamp": "2025-01-11T23:01:03.253Z"
  }
}
```

## Support

For API-related issues:
1. Check the logs in `sentix/logs/`
2. Verify configuration in `config.yml`
3. Test with simple requests first
4. Contact development team for advanced issues