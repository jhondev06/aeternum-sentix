# Sentix System Architecture

## Overview

Sentix is a comprehensive sentiment analysis platform for financial markets, designed to process news articles and social media data to generate actionable trading signals. The system leverages machine learning models to analyze sentiment and predict market movements.

## System Components

### 1. Data Ingestion Layer

**Purpose**: Collect and normalize raw data from multiple sources.

**Components**:
- **RSS Client** (`ingest/rss_client.py`): Fetches news articles from RSS feeds
- **Twitter Client** (`ingest/twitter_client.py`): Collects social media posts via Twitter API
- **Normalizer** (`ingest/normalize.py`): Standardizes text data and maps tickers

**Data Sources**:
- RSS feeds from financial news sites (InfoMoney, Valor, Bloomberg, etc.)
- Twitter API for real-time social sentiment
- Yahoo Finance for price data

### 2. Sentiment Analysis Engine

**Purpose**: Process text data through NLP models to extract sentiment scores.

**Components**:
- **FinBERT Model** (`sentiment/finbert.py`): Pre-trained financial sentiment analysis model
- **Batch Processing**: Handles multiple texts efficiently with configurable batch sizes

**Features**:
- Positive/Negative/Neutral classification
- Confidence scores for each sentiment category
- Support for Portuguese language content

### 3. Feature Aggregation Layer

**Purpose**: Transform raw sentiment scores into time-series features for modeling.

**Components**:
- **Aggregator** (`features/aggregate.py`): Groups sentiment data into time buckets
- **Time Decay**: Applies exponential decay to recent data points
- **Statistical Features**: Calculates mean, std, min, max, count for each bucket

**Configuration**:
- Bucket size (default: weekly)
- Decay half-life (default: 6 periods)
- Feature engineering for model input

### 4. Machine Learning Pipeline

**Purpose**: Train predictive models to forecast price movements.

**Components**:
- **Labeling Engine** (`backtest/label.py`): Creates training labels from price data
- **Probability Model** (`models/prob_model.py`): Logistic regression with isotonic calibration
- **Backtesting Framework** (`backtest/backtester.py`): Evaluates model performance

**Model Features**:
- Forward horizon prediction (configurable bars ahead)
- Probability calibration for better Brier scores
- Cross-validation and performance metrics

### 5. Real-time API Layer

**Purpose**: Provide programmatic access to sentiment analysis and signals.

**Components**:
- **FastAPI Application** (`api/app.py`): RESTful API with authentication
- **Endpoints**:
  - `/score_text`: Analyze individual text snippets
  - `/signal`: Get trading signals for tickers
  - `/realtime`: Fetch latest sentiment data
  - `/historical`: Query historical sentiment series

**Security**:
- HTTP Basic Authentication
- Configurable credentials
- GZip compression for responses

### 6. Alert System

**Purpose**: Monitor sentiment changes and trigger notifications.

**Components**:
- **Alert Engine** (`alerts/engine.py`): Core monitoring logic
- **Rule Engine** (`alerts/rule.py`): Configurable alert conditions
- **Webhook System** (`alerts/webhook.py`): External integrations
- **Logger** (`alerts/logger.py`): Alert history and statistics

**Features**:
- Customizable rules based on sentiment thresholds
- Webhook notifications to external systems
- Cooldown periods to prevent alert spam
- Comprehensive logging and monitoring

### 7. Visualization Dashboard

**Purpose**: Interactive exploration of sentiment data and signals.

**Components**:
- **Streamlit App** (`dashboard.py`): Web-based dashboard
- **Data Visualization**: Charts for sentiment evolution and price comparison
- **Filtering**: Date ranges and ticker selection

## Data Flow

```
Raw Data Sources
      ↓
Data Ingestion (RSS/Twitter)
      ↓
Text Normalization & Ticker Mapping
      ↓
Sentiment Analysis (FinBERT)
      ↓
Feature Aggregation (Time Buckets)
      ↓
Model Training & Backtesting
      ↓
Real-time API & Alerts
      ↓
Dashboard & External Integrations
```

## Configuration Management

**Central Configuration** (`config.yml`):
- Data sources and languages
- Model parameters and thresholds
- API authentication settings
- Alert system configuration

**Dynamic Configuration**:
- Ticker mappings (`tickers.yml`)
- Alert rules (via API)
- Webhook configurations (via API)

## Deployment Architecture

### Development Environment
- Local execution with `main.py`
- Streamlit dashboard on port 8501
- FastAPI server on port 8000

### Production Considerations
- Containerization with Docker
- Database integration for persistence
- Load balancing for API scaling
- Monitoring and logging infrastructure

## Technology Stack

- **Programming Language**: Python 3.8+
- **Web Framework**: FastAPI for API, Streamlit for dashboard
- **Machine Learning**: Transformers (FinBERT), scikit-learn
- **Data Processing**: pandas, numpy
- **Visualization**: Plotly, Streamlit
- **External APIs**: Twitter API, Yahoo Finance
- **Deployment**: Docker, cloud platforms

## Performance Characteristics

- **Throughput**: Configurable batch sizes for sentiment analysis
- **Latency**: Real-time processing for API requests
- **Storage**: CSV-based data persistence (suitable for MVP)
- **Scalability**: Modular design allows horizontal scaling

## Security Considerations

- API authentication with HTTP Basic
- Input validation and sanitization
- Secure credential management
- Rate limiting for API endpoints
- Audit logging for alert system

## Monitoring and Maintenance

- Comprehensive logging throughout the pipeline
- Alert system statistics and history
- Model performance tracking
- Data quality monitoring
- Automated retraining capabilities