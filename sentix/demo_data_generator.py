#!/usr/bin/env python3
"""
Demo Data Generator for Sentix
Generates sample financial news articles and sentiment data for demonstration purposes.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import uuid
import yaml
import os
from sentiment.finbert import FinBertSentiment
from features.aggregate import build_sentiment_bars

class DemoDataGenerator:
    def __init__(self, config_path='config.yml'):
        self.config_path = config_path
        self.load_config()

        # Initialize FinBERT
        self.finbert = FinBertSentiment(self.config['sentiment']['model_id'],
                                       self.config['sentiment']['batch_size'],
                                       self.config['sentiment'].get('device'))

    def load_config(self):
        """Load configuration"""
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)

    def generate_sample_articles(self, num_articles=100, days_back=30):
        """Generate sample financial news articles"""

        # Sample article templates
        article_templates = [
            # Positive news
            {
                "title": "{} announces record quarterly profits, stock surges",
                "body": "The company reported earnings that exceeded analyst expectations by 15%. Revenue grew by 22% year-over-year, driven by strong performance in key markets. The CEO stated that the company's strategic initiatives are paying off.",
                "sentiment": "positive"
            },
            {
                "title": "Analysts upgrade {} rating following strong earnings",
                "body": "Following yesterday's earnings report, multiple analysts have upgraded their ratings for the stock. The consensus price target has been raised by an average of 8%, reflecting confidence in the company's growth trajectory.",
                "sentiment": "positive"
            },
            {
                "title": "{} secures major contract worth R$ {} billion",
                "body": "The company has been awarded a significant contract that will contribute substantially to its revenue growth. This deal underscores the company's competitive position in the market.",
                "sentiment": "positive"
            },

            # Negative news
            {
                "title": "{} faces regulatory scrutiny over accounting practices",
                "body": "The company is under investigation by regulatory authorities regarding its accounting methods. This development has raised concerns among investors about potential financial restatements.",
                "sentiment": "negative"
            },
            {
                "title": "{} reports wider-than-expected losses",
                "body": "The company's quarterly results showed losses that were significantly higher than anticipated. Management cited challenging market conditions and increased competition as key factors.",
                "sentiment": "negative"
            },
            {
                "title": "Supply chain disruptions impact {} operations",
                "body": "The company is experiencing delays in its supply chain due to global logistics challenges. This has led to production slowdowns and increased operational costs.",
                "sentiment": "negative"
            },

            # Neutral news
            {
                "title": "{} announces dividend payment of R$ {} per share",
                "body": "The company's board has approved a dividend payment for the quarter. This represents a continuation of the company's shareholder-friendly policies.",
                "sentiment": "neutral"
            },
            {
                "title": "{} completes acquisition of smaller competitor",
                "body": "The company has successfully completed the acquisition of a regional competitor. This move is expected to strengthen the company's market position.",
                "sentiment": "neutral"
            },
            {
                "title": "Market analysis: {} sector outlook remains stable",
                "body": "Industry analysts maintain a neutral outlook for the sector. While there are opportunities for growth, challenges in the macroeconomic environment persist.",
                "sentiment": "neutral"
            }
        ]

        # Company/asset names
        entities = {
            "PETR4.SA": ["Petrobras", "Brazilian oil giant", "state-controlled oil company"],
            "VALE3.SA": ["Vale", "mining company", "iron ore producer"],
            "ITUB4.SA": ["Itaú", "Brazilian bank", "financial institution"],
            "BBDC4.SA": ["Bradesco", "banking group", "financial services company"],
            "WEGE3.SA": ["WEG", "industrial company", "equipment manufacturer"],
            "IPCA": ["Brazilian inflation", "consumer price index", "inflation rate"],
            "PIB": ["Brazilian economy", "GDP growth", "economic expansion"],
            "SELIC": ["Brazilian interest rates", "central bank policy", "monetary policy"]
        }

        articles = []
        base_date = datetime.now() - timedelta(days=days_back)

        for i in range(num_articles):
            # Random entity
            ticker = np.random.choice(list(entities.keys()))
            entity_names = entities[ticker]

            # Random template
            template = np.random.choice(article_templates)

            # Generate article
            published_at = base_date + timedelta(
                days=np.random.randint(0, days_back),
                hours=np.random.randint(0, 24),
                minutes=np.random.randint(0, 60)
            )

            # Fill template
            entity_name = np.random.choice(entity_names)
            amount = np.random.randint(1, 50) if "{}" in template["title"] else ""

            title = template["title"].format(entity_name, amount) if amount else template["title"].format(entity_name)
            body = template["body"].format(entity_name, amount) if amount else template["body"].format(entity_name)

            article = {
                "id": str(uuid.uuid4().hex),
                "ticker": ticker,
                "published_at": published_at.isoformat() + "Z",
                "title": title,
                "body": body,
                "url": f"https://demo-news.com/article/{i}",
                "lang": "pt",
                "source": "demo-news.com"
            }

            articles.append(article)

        return pd.DataFrame(articles)

    def generate_historical_prices(self, tickers, days_back=90):
        """Generate sample historical price data"""
        price_data = []

        for ticker in tickers:
            base_date = datetime.now() - timedelta(days=days_back)

            # Generate price series with some trend and volatility
            dates = [base_date + timedelta(days=i) for i in range(days_back)]

            if ticker in ["IPCA", "PIB", "SELIC"]:
                # Economic indicators - generate realistic values
                if ticker == "IPCA":
                    base_value = 4.5  # Base inflation rate
                    values = [base_value + np.random.normal(0, 0.5) for _ in dates]
                elif ticker == "PIB":
                    base_value = 2.0  # Base GDP growth
                    values = [base_value + np.random.normal(0, 0.3) for _ in dates]
                else:  # SELIC
                    base_value = 10.5  # Base interest rate
                    values = [base_value + np.random.normal(0, 0.8) for _ in dates]
            else:
                # Stock prices - generate realistic price movements
                base_price = 50.0 if "PETR4" in ticker else 30.0
                prices = [base_price]

                for _ in range(len(dates) - 1):
                    # Random walk with slight upward trend
                    change = np.random.normal(0.001, 0.02)  # 0.1% mean, 2% std
                    new_price = prices[-1] * (1 + change)
                    prices.append(max(new_price, 1.0))  # Floor at $1

                values = prices

            # Create forward returns for training
            fwd_returns = []
            for i in range(len(values)):
                if i < len(values) - 5:  # 5-day forward return
                    fwd_return = (values[i + 5] - values[i]) / values[i]
                else:
                    fwd_return = 0.0
                fwd_returns.append(fwd_return)

            for date, value, fwd_ret in zip(dates, values, fwd_returns):
                price_data.append({
                    "ticker": ticker,
                    "date": date,
                    "close": value,
                    "close_fwd": value * (1 + fwd_ret),
                    "r_fwd": fwd_ret
                })

        return pd.DataFrame(price_data)

    def create_training_set(self, articles_df, prices_df):
        """Create training set by combining sentiment and price data"""
        # Process articles through sentiment pipeline
        print("Processing articles through sentiment analysis...")

        # Save articles to temp file for processing
        articles_file = "data/demo_articles.csv"
        articles_df.to_csv(articles_file, index=False)

        # Build sentiment bars
        sentiment_df = build_sentiment_bars(articles_file, self.config['aggregation']['window'], self.config_path)

        # Merge with price data
        training_data = []

        for _, sent_row in sentiment_df.iterrows():
            ticker = sent_row['ticker']
            bucket_start = pd.to_datetime(sent_row['bucket_start'])

            # Find corresponding price data
            # Ensure timezone consistency
            bucket_start_naive = bucket_start.tz_localize(None) if bucket_start.tz else bucket_start
            price_mask = (
                (prices_df['ticker'] == ticker) &
                (prices_df['date'] >= bucket_start_naive) &
                (prices_df['date'] < bucket_start_naive + pd.Timedelta(days=7))
            )

            if not price_mask.any():
                continue

            price_row = prices_df[price_mask].iloc[0]

            training_row = {
                **sent_row.to_dict(),
                "close": price_row['close'],
                "close_fwd": price_row['close_fwd'],
                "r_fwd": price_row['r_fwd'],
                "y": 1 if price_row['r_fwd'] > 0.01 else 0  # Binary target
            }

            training_data.append(training_row)

        training_df = pd.DataFrame(training_data)

        # Clean up temp file
        if os.path.exists(articles_file):
            os.remove(articles_file)

        return training_df

    def generate_demo_data(self, num_articles=200, days_back=60):
        """Generate complete demo dataset"""
        print("Generating demo data...")

        # Generate articles
        print("Generating sample articles...")
        articles_df = self.generate_sample_articles(num_articles, days_back)

        # Generate prices
        print("Generating historical prices...")
        tickers = self.config['data']['price']['symbols']
        prices_df = self.generate_historical_prices(tickers, days_back)

        # Create training set
        print("Creating training set...")
        training_df = self.create_training_set(articles_df, prices_df)

        # Save all data
        print("Saving demo data...")
        articles_df.to_csv("data/demo_articles_full.csv", index=False)
        prices_df.to_csv("data/demo_prices.csv", index=False)
        training_df.to_csv("data/demo_training_set.csv", index=False)

        # Update main data files for demo
        articles_df.to_csv("data/articles_raw.csv", index=False)
        training_df.to_csv("data/training_set.csv", index=False)

        print(f"Generated {len(articles_df)} articles, {len(prices_df)} price points, {len(training_df)} training samples")

        return {
            "articles": articles_df,
            "prices": prices_df,
            "training": training_df
        }

if __name__ == "__main__":
    generator = DemoDataGenerator()
    data = generator.generate_demo_data(num_articles=300, days_back=90)
    print("Demo data generation complete!")