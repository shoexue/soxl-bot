import yfinance as yf
import pandas as pd
from pathlib import Path

Path("data").mkdir(exist_ok=True)

ticker = "SOXL"

df = yf.download(
    ticker,
    start="2010-01-01",
    auto_adjust=True,
    progress=False
)

df = df.dropna()

# Flatten columns if yfinance returns multi-index columns
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

df.to_csv("data/SOXL.csv")

print(df.head())
print(df.tail())
print(f"Saved {len(df)} rows to data/SOXL.csv")