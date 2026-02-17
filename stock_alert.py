import yfinance as yf
import pandas as pd
import requests
import json
from datetime import datetime

# ✅ 여기에 access_token 넣기
ACCESS_TOKEN = "YVccoWK1diEKSgpd5VMh_J4-zpgAwaGSAAAAAQoNIJsAAAGcZsOAQ_6hmr4nKm-b"

# ✅ 종목 리스트
tickers = ["NVDA", "AAPL", "TSLA"]

def fetch_stats(ticker, period="1y"):
    df = yf.download(ticker, period=period, auto_adjust=False, progress=False)
    if df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    close = df["Close"].astype(float)

    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()

    # MA60 유효한 마지막 거래일 기준
    last_idx = ma60.last_valid_index()
    if last_idx is None:
        return None

    pos = df.index.get_loc(last_idx)
    if pos < 5:
        return None

    close0 = float(close.iloc[pos])
    close1 = float(close.iloc[pos - 1])
    close5 = float(close.iloc[pos - 5])

    ma20v = float(ma20.iloc[pos])
    ma60v = float(ma60.iloc[pos])

    chg1d = (close0 / close1 - 1.0) * 100.0
    chg5d = (close0 / close5 - 1.0) * 100.0

    return close0, ma20v, ma60v, chg1d, chg5d


def arrow(up: bool):
    return "🟢↑" if up else "🔴↓"


def fmt_pct(x):
    return f"{x:+.2f}%"


def format_block(ticker, close, ma20, ma60, chg1d, chg5d):
    a20 = arrow(close >= ma20)
    a60 = arrow(close >= ma60)

    # 보기 편하게 “종목 하나 = 한 블록”
    return (
        f"{ticker}\n"
        f"종가: {close:.2f}\n"
        f"전일: {fmt_pct(chg1d)} | 주간(5D): {fmt_pct(chg5d)}\n"
        f"20일이평선: {ma20:.2f} {a20}\n"
        f"60일이평선: {ma60:.2f} {a60}\n"
    )


def split_messages(lines, limit=900):
    """
    카카오 메시지 길이 여유 있게 쪼개기(너무 길면 여러 번 보내기)
    """
    msgs = []
    buf = ""
    for line in lines:
        # 블록 사이 빈 줄 하나
        add = line + "\n"
        if len(buf) + len(add) > limit:
            if buf.strip():
                msgs.append(buf.strip())
            buf = line + "\n"
        else:
            buf += add
    if buf.strip():
        msgs.append(buf.strip())
    return msgs


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


def main():
    today = datetime.now().strftime("%m/%d %H:%M")
    header = f"📈 20/60 + 변동률 (전일/5D)  |  {today}"
    lines = [header, ""]  # 헤더 다음 한 줄 띄움

    for t in tickers:
        res = fetch_stats(t)
        if res is None:
            lines.append(f"\n데이터 없음/기간 부족\n")
            continue

        close, ma20, ma60, chg1d, chg5d = res
        lines.append(format_block(t, close, ma20, ma60, chg1d, chg5d))

    # 너무 길면 자동 분할 전송
    msgs = split_messages(lines, limit=900)

    # 콘솔 출력 + 카톡 전송
    for i, m in enumerate(msgs, start=1):
        if len(msgs) > 1:
            m = f"{m}\n\n({i}/{len(msgs)})"
        print("\n" + m + "\n" + "-" * 40)
        send_to_kakao(m)


if __name__ == "__main__":
    main()