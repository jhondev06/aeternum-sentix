import requests
import pandas as pd
import yaml
from models.prob_model import ProbModel
import os
import re

def send_alert(token: str, chat_id: str, msg: str) -> None:
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": msg}, timeout=10)
    except:
        pass  # fail silently

if __name__ == "__main__":
    # Load config
    with open('config.yml', 'r') as f:
        config = yaml.safe_load(f)

    if not config['telegram']['enabled']:
        exit(0)

    token = config['telegram']['token']
    chat_id = config['telegram']['chat_id']
    threshold_long = config['signals']['threshold_long']

    if not os.path.exists('outputs/prob_model.pkl') or not os.path.exists('data/sentiment_bars.csv') or not os.path.exists('data/articles_raw.csv'):
        exit(0)

    # Load model
    model = ProbModel.load('outputs/prob_model.pkl')

    # Read sentiment bars
    bars_df = pd.read_csv('data/sentiment_bars.csv')
    bars_df['bucket_start'] = pd.to_datetime(bars_df['bucket_start'])

    # Read articles
    articles_df = pd.read_csv('data/articles_raw.csv')
    articles_df['published_at'] = pd.to_datetime(articles_df['published_at'])
    articles_df['bucket_start'] = articles_df['published_at'].dt.floor(config['aggregation']['window'])

    # For each ticker, get latest bar
    for ticker in bars_df['ticker'].unique():
        last_bar = bars_df[bars_df['ticker'] == ticker].sort_values('bucket_start').iloc[-1]
        features = last_bar.to_frame().T
        feature_cols = [col for col in features.columns if re.match(r'(mean|std|min|max|count|unc|decay)', col)]
        prob = model.predict_proba(features[feature_cols])[0]

        if prob > threshold_long:
            # Get top 3 articles from this bucket
            bucket_articles = articles_df[(articles_df['ticker'] == ticker) & (articles_df['bucket_start'] == last_bar['bucket_start'])]
            top_articles = bucket_articles.head(3)

            msg = f"🚀 Signal for {ticker}: Prob Up {prob:.3f}\n\n"
            for _, art in top_articles.iterrows():
                msg += f"• {art['title']}\n{art['url']}\n\n"

            send_alert(token, chat_id, msg)