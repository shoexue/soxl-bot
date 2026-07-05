import pandas as pd

df = pd.read_csv("data/SOXL.csv", parse_dates=["Date"], index_col="Date")

lookback = 20

df["return_1d"] = df["Close"].pct_change()
df["ma_20"] = df["Close"].rolling(lookback).mean()
df["std_20"] = df["Close"].rolling(lookback).std()

# How far price is from its recent average
df["z_score"] = (df["Close"] - df["ma_20"]) / df["std_20"]

# First basic mean-reversion signal
df["signal"] = df["z_score"] < -2

df = df.dropna()
df.to_csv("data/SOXL_features.csv")

print(df[["Close", "ma_20", "z_score", "signal"]].tail(20))