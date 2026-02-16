import yfinance as yf
import pandas as pd

tickers = ["NVDA", "AAPL", "TSLA"]

def fetch_ma(ticker, period="6mo"):
    df = yf.download(ticker, period=period, auto_adjust=False, progress=False)
    if df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()

    df2 = df.dropna()
    if len(df2) == 0:
        return None

    last = df2.iloc[-1]
    close = float(last["Close"])
    ma20  = float(last["MA20"])
    ma60  = float(last["MA60"])
    return close, ma20, ma60


lines = ["📈 20/60일 이평선 체크"]

for t in tickers:
    res = fetch_ma(t)
    if res is None:
        lines.append(f"- {t}: 데이터 없음/기간 부족")
    else:
        close, ma20, ma60 = res
        pos20 = "↑" if close >= ma20 else "↓"
        pos60 = "↑" if close >= ma60 else "↓"
        lines.append(f"- {t}: 종가 {close:.2f} | MA20 {ma20:.2f}({pos20}) | MA60 {ma60:.2f}({pos60})")

msg = "\n".join(lines)
print(msg)