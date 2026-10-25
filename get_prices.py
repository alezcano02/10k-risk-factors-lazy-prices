# Daily adjusted prices (Yahoo Finance) of the companies in data/filings.csv and of the S&P 500 ETF (SPY)
import pandas as pd
import yfinance as yf

tickers = sorted(pd.read_csv("data/filings.csv")["ticker"].unique().tolist()) + ["SPY"]
yahoo = [t.replace(".", "-") for t in tickers]           # BRK.B is BRK-B in Yahoo
precios = yf.download(yahoo, start="2014-01-01", end="2026-10-22", auto_adjust=True, progress=False)["Close"]
precios.columns = [c.replace("-", ".") for c in precios.columns]
precios.to_parquet("data/prices.parquet")
print(precios.shape, precios.notna().sum().sort_values().head())
