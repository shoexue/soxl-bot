import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv(
    "data/SOXL_features.csv",
    parse_dates=["Date"],
    index_col="Date"
)

signals = df[df["signal"] == True]

plt.figure(figsize=(14, 7))

plt.plot(df.index, df["Close"], label="SOXL Close", linewidth=1)
plt.plot(df.index, df["ma_20"], label="20-Day Moving Average", linewidth=1)

plt.scatter(
    signals.index,
    signals["Close"],
    marker="v",
    s=40,
    label="Mean Reversion Signal"
)

plt.title("SOXL Mean Reversion Signals")
plt.xlabel("Date")
plt.ylabel("Price")
plt.legend()
plt.grid(True)

plt.show()