import yfinance as yf
import pandas as pd
from pathlib import Path

Path("data").mkdir(exist_ok=True)

tickers = {
    "QQQ": "QQQ",
    "SOXX": "SOXX",
    "VIX": "^VIX"
}

for name, ticker in tickers.items():

    df = yf.download(
        ticker,
        start="2021-01-01",
        auto_adjust=True,
        progress=False
    )

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.to_csv(f"data/{name}.csv")

    print(f"{name}: saved {len(df)} rows")