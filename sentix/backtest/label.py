import pandas as pd
import yfinance as yf

def make_labels(sent_bars_csv: str, horizon_bars: int, price_cfg: dict) -> pd.DataFrame:
    # Read sentiment bars
    sent_df = pd.read_csv(sent_bars_csv)
    sent_df['bucket_start'] = pd.to_datetime(sent_df['bucket_start'], utc=True)

    # Try to download prices via yfinance according to config, fallback to demo_prices.csv
    symbols = price_cfg.get('symbols', [])
    interval = price_cfg.get('interval', '1d')
    period = price_cfg.get('period', '1y')

    prices_df_list = []
    try:
        import yfinance as yf
        for sym in symbols:
            data = yf.download(sym, interval=interval, period=period, progress=False)
            if isinstance(data, pd.DataFrame) and not data.empty:
                data = data.reset_index()
                # Flatten MultiIndex columns if present
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.droplevel(1)
                # Determine date column name
                date_col = 'Datetime' if 'Datetime' in data.columns else ('Date' if 'Date' in data.columns else None)
                if date_col is None:
                    continue
                data[date_col] = pd.to_datetime(data[date_col])
                data['ticker'] = sym
                data.rename(columns={'Close': 'close', date_col: 'timestamp'}, inplace=True)
                # Make timezone aware (UTC)
                data['timestamp'] = data['timestamp'].dt.tz_localize('UTC')
                prices_df_list.append(data[['ticker', 'timestamp', 'close']])
        if prices_df_list:
            prices_df = pd.concat(prices_df_list, ignore_index=True)
        else:
            raise Exception('No price data downloaded')
    except Exception:
        # Fallback to demo prices
        prices_df = pd.read_csv('data/demo_prices.csv')
        prices_df['timestamp'] = pd.to_datetime(prices_df['date']).dt.tz_localize('UTC')
        prices_df = prices_df.rename(columns={'ticker': 'ticker', 'close': 'close'})
        prices_df = prices_df[['ticker', 'timestamp', 'close']]

    # Resample to weekly, taking last close of the week, aligned to Monday start
    prices_weekly = prices_df.set_index('timestamp').groupby('ticker').resample('W-MON', label='left', closed='left')['close'].last().reset_index()
    prices_weekly = prices_weekly.rename(columns={'timestamp': 'bucket_start'})

    # Merge
    merged = pd.merge(sent_df, prices_weekly, on=['ticker', 'bucket_start'], how='inner')

    # Compute forward return
    merged = merged.sort_values(['ticker', 'bucket_start'])
    merged['close_fwd'] = merged.groupby('ticker')['close'].shift(-horizon_bars)
    merged['r_fwd'] = (merged['close_fwd'] / merged['close']) - 1
    merged['y'] = (merged['r_fwd'] > 0).astype(int)

    # Drop rows with NaN r_fwd
    merged = merged.dropna(subset=['r_fwd'])

    # Write to CSV
    merged.to_csv('data/training_set.csv', index=False)
    return merged