import yaml
import re
import pandas as pd

def load_ticker_map(yaml_path: str) -> dict:
    with open(yaml_path, 'r') as f:
        return yaml.safe_load(f)

def map_entities(df: pd.DataFrame, ticker_map: dict) -> pd.DataFrame:
    # Compile regex for each ticker
    regex_map = {}
    for ticker, data in ticker_map.items():
        aliases = data['aliases']
        pattern = '|'.join(re.escape(alias) for alias in aliases)
        regex_map[ticker] = re.compile(pattern, re.IGNORECASE)

    # Function to find matching tickers for a row
    def find_tickers(row):
        text = (row['title'] or '') + ' ' + (row['body'] or '')
        matches = []
        for ticker, regex in regex_map.items():
            if regex.search(text):
                matches.append(ticker)
        return matches

    # Apply to each row
    df['tickers'] = df.apply(find_tickers, axis=1)

    # Filter out rows with no tickers
    df = df[df['tickers'].apply(len) > 0]

    # Explode to one row per article-ticker
    df = df.explode('tickers').rename(columns={'tickers': 'ticker'})

    # Keep only specified columns
    keep_cols = ['id', 'ticker', 'published_at', 'title', 'body', 'url', 'lang', 'source']
    return df[keep_cols]