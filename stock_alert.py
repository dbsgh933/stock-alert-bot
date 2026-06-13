
import yfinance as yf
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# 네이버 메일설정
NAVER_EMAIL = os.environ["NAVER_EMAIL"]
NAVER_APP_PASSWORD = os.environ["NAVER_APP_PASSWORD"]
TO_EMAIL = os.environ.get("TO_EMAIL", NAVER_EMAIL)

def load_tickers():

    with open(BASE_DIR / "tickers.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    portfolio_kr = list(data["portfolio"]["kr"].keys())
    portfolio_us = list(data["portfolio"]["us"].keys())

    watchlist_kr = list(data["watchlist"]["kr"].keys())
    watchlist_us = list(data["watchlist"]["us"].keys())

    ticker_name_map = {}

    ticker_name_map.update(data["portfolio"]["kr"])
    ticker_name_map.update(data["portfolio"]["us"])
    ticker_name_map.update(data["watchlist"]["kr"])
    ticker_name_map.update(data["watchlist"]["us"])

    return portfolio_kr, portfolio_us, watchlist_kr, watchlist_us, ticker_name_map

TICKERS_KR, TICKERS_US, WATCHLIST_KR, WATCHLIST_US, TICKER_NAME_MAP = load_tickers()

def fetch_stats(ticker, period="1y"):
    df = yf.download(ticker, period=period, auto_adjust=False, progress=False)
    if df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    close = df["Close"].astype(float)
    volume = df["Volume"].astype(float)

    ma5  = close.rolling(5).mean()
    ma10 = close.rolling(10).mean()
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

    ma5v  = float(ma5.iloc[pos])
    ma10v = float(ma10.iloc[pos])
    
    ma20v = float(ma20.iloc[pos])
    ma20_prev = float(ma20.iloc[pos - 1])
    
    ma60v = float(ma60.iloc[pos])
    ma60_prev = float(ma60.iloc[pos - 1])
    
    close_prev = float(close.iloc[pos - 1])
    
    # ✅ 20MA 아래→위 상향돌파
    cross20_up = (close_prev < ma20_prev) and (close0 >= ma20v)
    
    # ✅ 20MA 위→아래 하향이탈
    cross20_down = (close_prev >= ma20_prev) and (close0 < ma20v)
    
    # ✅ 60MA 위→아래 하향이탈
    cross60_down = (close_prev >= ma60_prev) and (close0 < ma60v)

    # 수익률
    chg1d  = (close0 / close1  - 1.0) * 100.0
    chg5d  = (close0 / close5  - 1.0) * 100.0
    chg20d = (close0 / close20 - 1.0) * 100.0
    chg60d = (close0 / close60 - 1.0) * 100.0

    # 거래량 배수(오늘 / 20일 평균)
    vol_today = float(volume.iloc[pos])
    vol_avg20 = float(vol_ma20.iloc[pos])
    vol_ratio = (vol_today / vol_avg20) if vol_avg20 and vol_avg20 > 0 else 0.0

    return close0, ma5v, ma10v, ma20v, ma60v, chg1d, chg5d, chg20d, chg60d, vol_ratio, cross20_up, cross20_down, cross60_down

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

def format_block(ticker, close, ma5, ma10, ma20, ma60, chg1d, chg5d, chg20d, chg60d, vol_ratio, cross20_up, cross20_down, cross60_down):
    name = TICKER_NAME_MAP.get(ticker, ticker)

    signals = []

    if cross60_down:
        signals.append("🚨60이탈")
    if cross20_down:
        signals.append("⚠️20이탈")
    if cross20_up and vol_ratio >= 2.0:
        signals.append("🚀20돌파")
    elif cross20_up:
        signals.append("⭐20돌파")

    signal_text = " ".join(signals)
    display_name = f"{signal_text} {name} ({ticker})".strip()

    action_msg = ""
    trend_msg = ""
    if close >= ma5 >= ma10 >= ma20 >= ma60:
        trend_msg = "추세: 5/10/20/60 정배열"
    elif ma5 >= ma10 >= ma20 >= ma60:
        trend_msg = "추세: 이평선 정배열, 현재가 5일선 아래"
    elif ma20 >= ma60:
        trend_msg = "추세: 중기 상승 구조"
    else:
        trend_msg = "추세: 정배열 아님"

    if cross60_down:
        action_msg = "판단: 전량 매도 고려"
    elif cross20_down:
        action_msg = "판단: 30% 매도 고려"
    elif cross20_up:
        action_msg = "판단: 매수 고려"

    return (
        f"{display_name}\n"
        f"{action_msg + chr(10) if action_msg else ''}"
        f"{trend_msg}\n"
        f"종가: {format_price(ticker, close)}\n"
        f"전일: {fmt_pct_dot(chg1d)} | 주간(5D): {fmt_pct_dot(chg5d)}\n"
        f"20D: {fmt_pct_dot(chg20d)} | 60D: {fmt_pct_dot(chg60d)}\n"
        f"5일이평선:  {format_price(ticker, ma5)} {ma_flag(close, ma5)}\n"
        f"10일이평선: {format_price(ticker, ma10)} {ma_flag(close, ma10)}\n"
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

def send_to_email(text: str):
    subject = "📈 Stock Alert Bot"

    body = (
        "📈 Stock Alert Bot\n"
        "--------------------\n"
        f"{text}"
    )

    recipients = [email.strip() for email in TO_EMAIL.split(",") if email.strip()]

    msg = MIMEMultipart()
    msg["From"] = NAVER_EMAIL
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.naver.com", 465) as server:
        server.login(NAVER_EMAIL, NAVER_APP_PASSWORD)
        server.send_message(
            msg,
            from_addr=NAVER_EMAIL,
            to_addrs=recipients
        )

    print(f"Email sent to {', '.join(recipients)}")


def build_section_lines(title: str, tickers: list[str]):
    lines = [title]
    results = []
    missing = []
    event_list = {
        "cross20_up": [],
        "cross20_up_volume": [],
        "cross20_down": [],
        "cross60_down": [],
    }

    for t in tickers:
        res = fetch_stats(t)
        if res is None:
            missing.append(t)
            continue

        close, ma5, ma10, ma20, ma60, chg1d, chg5d, chg20d, chg60d, vol_ratio, cross20_up, cross20_down, cross60_down = res

        # ✅ 이벤트 감지 - 상향/하향/20일/60일 분리
        name = TICKER_NAME_MAP.get(t, t)
        
        if cross20_up:
            if vol_ratio >= 2.0:
                event_list["cross20_up_volume"].append(
                    f"- {name} ({t}) | 매수 적극 검토"
                )
            else:
                event_list["cross20_up"].append(
                    f"- {name} ({t}) | 매수 고려"
                )
        
        if cross20_down:
            event_list["cross20_down"].append(
                f"- {name} ({t}) | 30% 매도 고려"
            )
        
        if cross60_down:
            event_list["cross60_down"].append(
                f"- {name} ({t}) | 전량 매도 고려"
            )

        above60 = close >= ma60
        above20 = close >= ma20

        is_aligned = close >= ma5 >= ma10 >= ma20 >= ma60
        ma_score = 0
        
        if close >= ma5:
            ma_score += 1
        if ma5 >= ma10:
            ma_score += 1
        if ma10 >= ma20:
            ma_score += 1
        if ma20 >= ma60:
            ma_score += 1
        
        results.append({
            "ticker": t,
            "close": close,
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "ma60": ma60,
            "chg1d": chg1d,
            "chg5d": chg5d,
            "chg20d": chg20d,
            "chg60d": chg60d,
            "vol_ratio": vol_ratio,
            "above60": close >= ma60,
            "above20": close >= ma20,
            "is_aligned": is_aligned,
            "ma_score": ma_score,
            "cross20_up": cross20_up,
            "cross20_down": cross20_down,
            "cross60_down": cross60_down,
        })

    # 현재가 > 5일선 > 10일선 > 20일선 > 60일선
    # 20일선 위
    # 60일선 위
    # 20D 수익률 양호
    # 5D 수익률 양호
    results.sort(
        key=lambda x: (
            x["is_aligned"],   # 완전 정배열 우선
            x["ma_score"],     # 정배열에 가까운 순
            x["above20"],      # 20일선 위
            x["above60"],      # 60일선 위
            x["chg20d"],       # 20일 수익률
            x["chg5d"],        # 5일 수익률
            x["chg1d"],        # 1일 수익률
        ),
        reverse=True
    )

    for r in results:
        lines.append(format_block(
            r["ticker"], r["close"],
            r["ma5"], r["ma10"], r["ma20"], r["ma60"],
            r["chg1d"], r["chg5d"], r["chg20d"], r["chg60d"],
            r["vol_ratio"], r["cross20_up"], r["cross20_down"], r["cross60_down"]
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

   sort_guide = [
        "📊 전략/정렬 기준",
        "전략: GDP·산업 성장을 이끄는 주도주 중심 추세추종",
        "주식 비중: 주도주 존재 + 상승 추세 확인 시 확대, 주도주 부재/추세 훼손 시 축소",
        "",
        "📈 종목 해석 기준",
        "정배열: 현재가 ≥ 5일선 ≥ 10일선 ≥ 20일선 ≥ 60일선",
        "상단 = 비중 확대 후보",
        "중간 = 관망 후보",
        "하단 = 비중 축소 후보",
        "20일선 하향이탈 = 일부 매도 검토",
        "60일선 하향이탈 = 강한 매도 검토",
        "20일선 상향돌파 = 재매수/추가매수 후보",
        "",
        "💰 전체 주식 비중 기준",
        "주도주 없음 + 지수 20/60일선 아래 = 주식 비중 0~30%",
        "주도주 일부 있음 + 지수 애매함 = 주식 비중 30~60%",
        "주도주 다수 정배열 + 지수 20/60일선 위 = 주식 비중 60~90%",
        "주도주 강함 + 거래량 동반 + 시장 확산 = 주식 비중 90~100%",
        "",
        "정렬: 정배열 → 근접도 → 20일선 위 → 60일선 위 → 20D/5D/1D 수익률",
        "",
    ]
    
    lines = [header, ""] + sort_guide

    # ✅ 이벤트를 종류별로 분리해서 저장
    all_events = {
        "cross20_up": [],
        "cross20_up_volume": [],
        "cross20_down": [],
        "cross60_down": [],
    }

    section_lines, events = build_section_lines("📦 PORTFOLIO - 🇰🇷 KOREA", TICKERS_KR)
    lines += section_lines
    for key in all_events:
        all_events[key] += events[key]

    section_lines, events = build_section_lines("📦 PORTFOLIO - 🇺🇸 USA", TICKERS_US)
    lines += section_lines
    for key in all_events:
        all_events[key] += events[key]

    section_lines, events = build_section_lines("👀 WATCHLIST - 🇰🇷 KOREA", WATCHLIST_KR)
    lines += section_lines
    for key in all_events:
        all_events[key] += events[key]

    section_lines, events = build_section_lines("👀 WATCHLIST - 🇺🇸 USA", WATCHLIST_US)
    lines += section_lines
    for key in all_events:
        all_events[key] += events[key]

    # ✅ 요약 메시지 생성
    summary = ["📌 오늘 주요 이벤트", ""]

    has_event = any(len(v) > 0 for v in all_events.values())

    if not has_event:
        summary.append("오늘 주요 이벤트 없음")
        summary.append("")
    else:
        if all_events["cross20_up_volume"]:
            summary.append("🚀 20일선 상향돌파 + 거래량")
            summary += all_events["cross20_up_volume"]
            summary.append("")

        if all_events["cross20_up"]:
            summary.append("⭐ 20일선 상향돌파")
            summary += all_events["cross20_up"]
            summary.append("")

        if all_events["cross20_down"]:
            summary.append("⚠️ 20일선 하향이탈")
            summary += all_events["cross20_down"]
            summary.append("")

        if all_events["cross60_down"]:
            summary.append("🚨 60일선 하향이탈")
            summary += all_events["cross60_down"]
            summary.append("")

    lines = [lines[0], ""] + summary + lines[2:]

    # ✅ 메일은 한 번에 발송
    message = "\n".join(lines)

    print("\n" + message + "\n" + "-" * 40)
    send_to_email(message)

if __name__ == "__main__":
    main()
