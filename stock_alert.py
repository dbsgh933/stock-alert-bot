import yfinance as yf
import pandas as pd
import requests
import json
import os
from datetime import datetime
import pytz

REST_API_KEY = os.environ["KAKAO_REST_API_KEY"]
REFRESH_TOKEN = os.environ["KAKAO_REFRESH_TOKEN"]
print("REST len:", len(os.getenv("KAKAO_REST_API_KEY","")))
print("REFRESH len:", len(os.getenv("KAKAO_REFRESH_TOKEN","")))

def get_access_token():
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": REST_API_KEY,
        "refresh_token": REFRESH_TOKEN,
    }
    r = requests.post(url, data=data, timeout=15)
    result = r.json()
    print("REFRESH RESULT:", result)
    if r.status_code != 200:
        raise RuntimeError(f"Failed to refresh token: {r.status_code} {result}")

    access_token = result.get("access_token")
    if not access_token:
        raise RuntimeError(f"No access_token in response: {result}")
    print("refresh status:", r.status_code)
    print("refresh response keys:", list(result.keys()))

    return access_token

ACCESS_TOKEN = get_access_token()

if not ACCESS_TOKEN:
    raise RuntimeError("Failed to refresh Kakao access token. Check KAKAO_REST_API_KEY / KAKAO_REFRESH_TOKEN.")

# ✅ 종목 리스트
tickers = ["NVDA", "TSLA", "CRWV", "CAT", "GOOG", "LLY", "WDC", "TER", "ICOP", "SNDK", "MU", "IAU", "SLV", "COHR", "CMI", "LRCX", "TSM", "RKLB" ]

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
print("REST_API_KEY set:", bool(os.getenv("KAKAO_REST_API_KEY")))
print("REFRESH_TOKEN set:", bool(os.getenv("KAKAO_REFRESH_TOKEN")))


def main():
    today = datetime.now().strftime("%m/%d %H:%M")
    header = f"📈 20/60 + 변동률 (전일/5D)  |  {today}"
    lines = [header, ""]

    results = []
    missing = []

    for t in tickers:
        res = fetch_stats(t)
        if res is None:
            missing.append(t)
            continue

        close, ma20, ma60, chg1d, chg5d = res
        above60 = close >= ma60
        above20 = close >= ma20

        # (정렬용 키 + 출력용 데이터) 저장
        results.append({
            "ticker": t,
            "close": close,
            "ma20": ma20,
            "ma60": ma60,
            "chg1d": chg1d,
            "chg5d": chg5d,
            "above60": above60,
            "above20": above20,
        })

    # ✅ (60일선 위) → (20일선 위) → (5일 변동률) 순 정렬
    results.sort(key=lambda x: (x["above60"], x["above20"], x["chg5d"]), reverse=True)

    # 출력
    for r in results:
        lines.append(format_block(
            r["ticker"], r["close"], r["ma20"], r["ma60"], r["chg1d"], r["chg5d"]
        ))

    # 데이터 부족한 종목은 맨 아래에 몰아서 표시
    if missing:
        lines.append("⚠️ 데이터 없음/기간 부족")
        for t in missing:
            lines.append(f"- {t}")

    # 너무 길면 자동 분할 전송
    msgs = split_messages(lines, limit=900)

    for i, m in enumerate(msgs, start=1):
        if len(msgs) > 1:
            m = f"{m}\n\n({i}/{len(msgs)})"
        print("\n" + m + "\n" + "-" * 40)
        send_to_kakao(m)


if __name__ == "__main__":
    main()