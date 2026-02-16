import yfinance as yf
import pandas as pd
import requests
import json

ACCESS_TOKEN = "YVccoWK1diEKSgpd5VMh_J4-zpgAwaGSAAAAAQoNIJsAAAGcZsOAQ_6hmr4nKm-b"

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
    return float(last["Close"]), float(last["MA20"]), float(last["MA60"])

def fetch_stats(ticker, period="1y"):
    df = yf.download(ticker, period=period, auto_adjust=False, progress=False)
    if df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    close = df["Close"].astype(float)

    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()

    # MA60이 유효한 마지막 날짜를 기준으로 잡기
    last_idx = ma60.last_valid_index()
    if last_idx is None:
        return None

    pos = df.index.get_loc(last_idx)
    if pos < 5:  # 5거래일 전 비교용
        return None

    close0 = float(close.iloc[pos])
    close1 = float(close.iloc[pos - 1])
    close5 = float(close.iloc[pos - 5])

    ma20v = float(ma20.iloc[pos])
    ma60v = float(ma60.iloc[pos])

    chg1d = (close0 / close1 - 1.0) * 100.0
    chg5d = (close0 / close5 - 1.0) * 100.0

    return close0, ma20v, ma60v, chg1d, chg5d

def send_to_kakao(text: str):
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    data = {
        "template_object": json.dumps({
            "object_type": "text",
            "text": text[:1000],
            "link": {"web_url": "https://finance.yahoo.com"}
        }, ensure_ascii=False)
    }
    r = requests.post(url, headers=headers, data=data)
    print(r.status_code, r.text)

lines = ["📈 20/60일 + 변동률 체크(전일/5거래일)"]

for t in tickers:
    res = fetch_stats(t)
    if res is None:
        lines.append(f"- {t}: 데이터 없음/기간 부족")
        continue

    close, ma20, ma60, chg1d, chg5d = res
    pos20 = "↑" if close >= ma20 else "↓"
    pos60 = "↑" if close >= ma60 else "↓"

    lines.append(
        f"- {t}: {close:.2f} | 1D {chg1d:+.2f}% | 5D {chg5d:+.2f}% | "
        f"MA20 {ma20:.2f}({pos20}) | MA60 {ma60:.2f}({pos60})"
    )

msg = "\n".join(lines)
print(msg)
send_to_kakao(msg)