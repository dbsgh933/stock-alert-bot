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

# 🔹 티커 → 회사명 매핑
TICKER_NAME_MAP = {

    # 🇺🇸 미국
    "NVDA": "엔비디아",
  #  "CRWV": "코어위브",
  #  "CAT": "캐터필러",
    "GOOG": "알파벳",
    "LLY": "일라이릴리",
    "WDC": "웨스턴디지털",
    "TER": "테라다인",
    "ICOP": "아이셰어즈 코퍼 ETF",
    "SNDK": "샌디스크",
    "MU": "마이크론",
    "IAU": "아이셰어즈 골드 ETF",
    "SLV": "아이셰어즈 실버 ETF",
    "COHR": "코히런트",
    "CMI": "커민스",
    "LRCX": "램리서치",
    "TSM": "TSMC",
 #   "JOBY": "조비에비에이션",
 #   "SMR": "뉴스케일파워",
    "GEV": "GE 버노바", 
    "RKLB": "로켓랩",
    "ETN": "이튼",
    "VXX": "VXX (VIX 단기선물 ETF)",

    # 🇰🇷 한국
    "004020.KS": "현대제철",
    "000120.KS": "CJ대한통운",
    "241180.KS": "TIGER 일본니케이225",
    "006800.KS": "미래에셋증권",
    "042660.KS": "한화오션",
    "352820.KS": "하이브",
    "005380.KS": "현대차",
    "009150.KS": "삼성전기",
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스",
    "034020.KS": "두산에너빌리티",
    "032830.KS": "삼성생명",
    "316140.KS": "우리금융지주",
    "086790.KS": "하나금융지주",
    "396500.KS": "TIGER 차이나반도체FACTSET",
    "272210.KS": "한화시스템",
    "079550.KS": "LIG넥스원",
    "010120.KS": "LS ELECTRIC",

     # 관심종목 미국
    "GS": "골드만삭스",
    "META": "메타",
    "IONQ": "아이온큐",
    "TSLA": "테슬라",
    "PLTR": "팔란티어",
    "AVGO": "브로드컴",
    "TLN": "탈런에너지",
    "SPOT": "스포티파이",
    "AAPL": "애플",
    "BITX": "비트코인 전략 2배 ETF",
    
    # 관심종목 한국
    "012450.KS": "한화에어로스페이스",
    "278470.KS": "에이피알",
    "298040.KS": "효성중공업",
    "267260.KS": "HD현대일렉트릭",
    "000810.KS": "삼성화재",
    "329180.KS": "HD현대중공업",   
}


# ✅ 종목 리스트
TICKERS_US = [
    "NVDA",   # 엔비디아
    "GOOG",   # 알파벳 Class C (구글)
    "LLY",    # 일라이 릴리
    "WDC",    # 웨스턴디지털
    "TER",    # 테라다인
    "ICOP",   # 아이코어커넥트
    "SNDK",   # 샌디스크
    "MU",     # 마이크론 테크놀로지
    "IAU",    # 아이셰어즈 골드 ETF
    "SLV",    # 아이셰어즈 실버 ETF
    "COHR",   # 코히런트
    "LRCX",   # 램리서치
    "TSM",    # TSMC (대만반도체)
   # "JOBY",   # 조비 에비에이션
   # "SMR",    # 뉴스케일파워
    "GEV",    # GE 버노바 
    "RKLB",  # 로켓랩
    "ETN",   # 이튼
    "SPOT",  # 스포티파이
    "VXX",
]
WATCHLIST_US = [
    "GS",    # 골드만삭스
    "META",  # 메타
    "IONQ",  # 아이온큐
    "TSLA",  # 테슬라
    "PLTR",  # 팔란티어
    "AVGO",  # 브로드컴
    "TLN",   # 탈런에너지
    "AAPL",  # 애플
    "CMI",    # 커민스
    "BITX",  # 비트코인 2배 레버리지 ETF
    "CRWV",   # 코어위브 
    "CAT",    # 캐터필러
]
TICKERS_KR = [
    "004020.KS",  # 현대제철
    "000120.KS",  # CJ대한통운
    "241180.KS",  # TIGER 일본니케이225
    "006800.KS",  # 미래에셋증권
    "042660.KS",  # 한화오션
    "352820.KS",  # 하이브
    "005380.KS",  # 현대차
    "009150.KS",  # 삼성전기
    "005930.KS",  # 삼성전자
    "000660.KS",  # SK하이닉스
    "034020.KS",  # 두산에너빌리티
    "032830.KS",  # 삼성생명
    "316140.KS",  # 우리금융지주
    "086790.KS",  # 하나금융지주
    "396500.KS",  # TIGER 차이나반도체FACTSET
    "278470.KS",  # 에이피알
]
WATCHLIST_KR = [
    "012450.KS",  # 한화에어로스페이스
    "010120.KS",  # LS ELECTRIC
    "298040.KS",  # 효성중공업
    "267260.KS",  # HD현대일렉트릭
    "000810.KS",  # 삼성화재
    "329180.KS",  # HD현대중공업
    "272210.KS",  # 한화시스템
    "079550.KS",  # LIG넥스원
]

def fetch_stats(ticker, period="1y"):
    df = yf.download(ticker, period=period, auto_adjust=False, progress=False)
    if df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    close = df["Close"].astype(float)
    volume = df["Volume"].astype(float)

    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    vol_ma20 = volume.rolling(20).mean()

    last_idx = ma60.last_valid_index()
    if last_idx is None:
        return None

    pos = df.index.get_loc(last_idx)
    if pos < 60:
        return None

    close0  = float(close.iloc[pos])
    close1  = float(close.iloc[pos - 1])
    close5  = float(close.iloc[pos - 5])
    close20 = float(close.iloc[pos - 20])
    close60 = float(close.iloc[pos - 60])

    ma20v = float(ma20.iloc[pos])
    ma20_prev = float(ma20.iloc[pos - 1])
    
    ma60v = float(ma60.iloc[pos])

    close0 = float(close.iloc[pos])
    close_prev = float(close.iloc[pos - 1])
    
    # ✅ 20MA 아래→위 상향돌파
    cross20_up = (close_prev < ma20_prev) and (close0 >= ma20v)

    # 수익률
    chg1d  = (close0 / close1  - 1.0) * 100.0
    chg5d  = (close0 / close5  - 1.0) * 100.0
    chg20d = (close0 / close20 - 1.0) * 100.0
    chg60d = (close0 / close60 - 1.0) * 100.0

    # 거래량 배수(오늘 / 20일 평균)
    vol_today = float(volume.iloc[pos])
    vol_avg20 = float(vol_ma20.iloc[pos])
    vol_ratio = (vol_today / vol_avg20) if vol_avg20 and vol_avg20 > 0 else 0.0

    return close0, ma20v, ma60v, chg1d, chg5d, chg20d, chg60d, vol_ratio, cross20_up

def fmt_pct_dot(x: float) -> str:
    # 변화량: 🟢+1.23% / 🔴-0.45%
    if x > 0:
        return f"🟢{x:+.2f}%"
    elif x < 0:
        return f"🔴{x:+.2f}%"
    else:
        return f"{x:+.2f}%"

def ma_flag(close: float, ma: float) -> str:
    # 이평선 위/아래: 🟢▲ / 🔴▼
    return "🟢▲" if close >= ma else "🔴▼"

def vol_badge(vol_ratio: float) -> str:
    # VOL 배지: 2.0x↑ 🔥, 1.5x↑ ⚡, 0.7x↓ 💧
    if vol_ratio >= 2.0:
        return "🔥"
    if vol_ratio >= 1.5:
        return "⚡"
    if vol_ratio <= 0.7:
        return "💧"
    return ""

def format_block(ticker, close, ma20, ma60, chg1d, chg5d, chg20d, chg60d, vol_ratio, cross20_up):
    name = TICKER_NAME_MAP.get(ticker, ticker)
    star = "⭐ " if cross20_up else ""
    display_name = f"{star}{name} ({ticker})"

    return (
        f"{display_name}\n"
        f"종가: {format_price(ticker, close)}\n"
        f"전일: {fmt_pct_dot(chg1d)} | 주간(5D): {fmt_pct_dot(chg5d)}\n"
        f"20D: {fmt_pct_dot(chg20d)} | 60D: {fmt_pct_dot(chg60d)}\n"
        f"20일이평선: {format_price(ticker, ma20)} {ma_flag(close, ma20)}\n"
        f"60일이평선: {format_price(ticker, ma60)} {ma_flag(close, ma60)}\n"
        f"거래량(20D평균대비): {vol_ratio:.2f}x {vol_badge(vol_ratio)}\n"
    )
    
def format_price(ticker, price):
    # 한국 주식
    if ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return f"{price:,.0f}원"
    # 미국 주식
    else:
        return f"${price:,.2f}"

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

    pretty = (
        "📈 Stock Alert Bot\n"
        "--------------------\n"
        f"{text}"
    )

    data = {
        "template_object": json.dumps({
            "object_type": "text",
            "text": pretty[:1000],  # 길이 안전장치
            "link": {
                "web_url": "https://www.tradingview.com",
                "mobile_web_url": "https://www.tradingview.com"
            }
        }, ensure_ascii=False)
    }

    r = requests.post(url, headers=headers, data=data, timeout=15)
    print(r.status_code, r.text)


def build_section_lines(title: str, tickers: list[str]):
    lines = [title]
    results = []
    missing = []
    event_list = []

    for t in tickers:
        res = fetch_stats(t)
        if res is None:
            missing.append(t)
            continue

        close, ma20, ma60, chg1d, chg5d, chg20d, chg60d, vol_ratio, cross20_up = res

        # ✅ 이벤트 감지 (⭐ / 🚀)
        name = TICKER_NAME_MAP.get(t, t)
        if cross20_up:
            if vol_ratio >= 2.0:
                event_list.append(f"🚀 {name} ({t})")
            else:
                event_list.append(f"⭐ {name} ({t})")

        above60 = close >= ma60
        above20 = close >= ma20

        results.append({
            "ticker": t,
            "close": close,
            "ma20": ma20,
            "ma60": ma60,
            "chg1d": chg1d,
            "chg5d": chg5d,
            "chg20d": chg20d,
            "chg60d": chg60d,
            "vol_ratio": vol_ratio, 
            "above60": above60,
            "above20": above20,
            "cross20_up": cross20_up,
        })

    # (20D → 5D → 1D)
    results.sort(
        key=lambda x: (x["chg20d"], x["chg5d"], x["chg1d"]),
        reverse=True
    )

    for r in results:
        lines.append(format_block(
            r["ticker"], r["close"], r["ma20"], r["ma60"],
            r["chg1d"], r["chg5d"], r["chg20d"], r["chg60d"],
            r["vol_ratio"], r["cross20_up"]
        ))

    if missing:
        lines.append("⚠️ 데이터 없음/기간 부족")
        for t in missing:
            lines.append(f"- {t}")

    lines.append("")
    return lines, event_list


def main():
    from datetime import datetime, timedelta
    now_kst = datetime.utcnow() + timedelta(hours=9)
    today = now_kst.strftime("%m/%d %H:%M")

    header = f"📈 20/60MA + 변동률(1D/5D/20D/60D) | {today}"
    lines = [header, ""]
    all_events = []

    # 섹션들 생성 + 이벤트 모으기
    section_lines, events = build_section_lines("📦 PORTFOLIO - 🇰🇷 KOREA", TICKERS_KR)
    lines += section_lines
    all_events += events

    section_lines, events = build_section_lines("📦 PORTFOLIO - 🇺🇸 USA", TICKERS_US)
    lines += section_lines
    all_events += events

    section_lines, events = build_section_lines("👀 WATCHLIST - 🇰🇷 KOREA", WATCHLIST_KR)
    lines += section_lines
    all_events += events

    section_lines, events = build_section_lines("👀 WATCHLIST - 🇺🇸 USA", WATCHLIST_US)
    lines += section_lines
    all_events += events

    # ✅ 이벤트 요약을 "맨 위"에 삽입 (header 다음 줄)
    if all_events:
        summary = ["⭐ 오늘 20MA 상향돌파"] + all_events + [""]
    else:
        summary = ["⭐ 오늘 20MA 상향돌파: 없음", ""]

    # header 바로 아래에 끼워넣기
    lines = [lines[0], ""] + summary + lines[2:]

    # 너무 길면 자동 분할 전송
    msgs = split_messages(lines, limit=900)

    for i, m in enumerate(msgs, start=1):
        if len(msgs) > 1:
            m = f"{m}\n\n({i}/{len(msgs)})"
        print("\n" + m + "\n" + "-" * 40)
        send_to_kakao(m)


if __name__ == "__main__":
    main()
