import yfinance as yf
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).resolve().parent

# 네이버 메일 설정
NAVER_EMAIL = os.environ["NAVER_EMAIL"]
NAVER_APP_PASSWORD = os.environ["NAVER_APP_PASSWORD"]
TO_EMAIL = os.environ.get("TO_EMAIL", NAVER_EMAIL)


# =========================
# 기본 설정
# =========================

MARKET_INDEX = {
    "kr": "^KS11",       # KOSPI
    "us": "^IXIC",      # NASDAQ Composite
    "semi": "SOXX",     # 반도체 ETF
}

MARKET_NAME = {
    "kr": "KOSPI",
    "us": "NASDAQ",
    "semi": "SOXX",
}


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


# =========================
# 데이터 수집
# =========================

def fetch_stats(ticker, period="1y"):
    df = yf.download(ticker, period=period, auto_adjust=False, progress=False)

    if df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    close = df["Close"].astype(float)
    volume = df["Volume"].astype(float)

    ma5 = close.rolling(5).mean()
    ma10 = close.rolling(10).mean()
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    vol_ma20 = volume.rolling(20).mean()

    last_idx = ma60.last_valid_index()

    if last_idx is None:
        return None

    pos = df.index.get_loc(last_idx)

    if pos < 61:
        return None

    close0 = float(close.iloc[pos])
    close1 = float(close.iloc[pos - 1])
    close5 = float(close.iloc[pos - 5])
    close20 = float(close.iloc[pos - 20])
    close60 = float(close.iloc[pos - 60])

    ma5v = float(ma5.iloc[pos])
    ma10v = float(ma10.iloc[pos])
    ma20v = float(ma20.iloc[pos])
    ma60v = float(ma60.iloc[pos])

    ma20_prev = float(ma20.iloc[pos - 1])
    ma60_prev = float(ma60.iloc[pos - 1])

    close_prev = float(close.iloc[pos - 1])

    # 이벤트 감지
    cross20_up = (close_prev < ma20_prev) and (close0 >= ma20v)
    cross20_down = (close_prev >= ma20_prev) and (close0 < ma20v)
    cross60_down = (close_prev >= ma60_prev) and (close0 < ma60v)

    # 수익률
    chg1d = (close0 / close1 - 1.0) * 100.0
    chg5d = (close0 / close5 - 1.0) * 100.0
    chg20d = (close0 / close20 - 1.0) * 100.0
    chg60d = (close0 / close60 - 1.0) * 100.0

    # 이평선 기울기
    ma20_slope = (ma20v / ma20_prev - 1.0) * 100.0
    ma60_slope = (ma60v / ma60_prev - 1.0) * 100.0

    # 이격도
    dist_ma20 = (close0 / ma20v - 1.0) * 100.0
    dist_ma60 = (close0 / ma60v - 1.0) * 100.0

    # 거래량
    vol_today = float(volume.iloc[pos])
    vol_avg20 = float(vol_ma20.iloc[pos])
    vol_ratio = (vol_today / vol_avg20) if vol_avg20 and vol_avg20 > 0 else 0.0

    return {
        "ticker": ticker,
        "close": close0,
        "ma5": ma5v,
        "ma10": ma10v,
        "ma20": ma20v,
        "ma60": ma60v,
        "chg1d": chg1d,
        "chg5d": chg5d,
        "chg20d": chg20d,
        "chg60d": chg60d,
        "ma20_slope": ma20_slope,
        "ma60_slope": ma60_slope,
        "dist_ma20": dist_ma20,
        "dist_ma60": dist_ma60,
        "vol_ratio": vol_ratio,
        "cross20_up": cross20_up,
        "cross20_down": cross20_down,
        "cross60_down": cross60_down,
        "above5": close0 >= ma5v,
        "above10": close0 >= ma10v,
        "above20": close0 >= ma20v,
        "above60": close0 >= ma60v,
        "is_aligned": close0 >= ma5v >= ma10v >= ma20v >= ma60v,
    }


# =========================
# 점수 계산
# =========================

def get_market_key(ticker: str) -> str:
    if ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return "kr"

    semi_keywords = [
        "NVDA", "AMD", "MU", "TSM", "LRCX", "ASML", "AMAT",
        "WDC", "ARM", "MRVL", "DELL", "AVGO", "TER", "COHR",
        "SOXX", "INTC"
    ]

    clean_ticker = ticker.replace(".US", "").upper()

    if clean_ticker in semi_keywords:
        return "semi"

    return "us"


def calc_stock_score(stats, market_stats):
    score = 0

    # 1. 정배열 구조
    if stats["is_aligned"]:
        score += 25
    else:
        if stats["above20"]:
            score += 8
        if stats["above60"]:
            score += 8
        if stats["ma5"] >= stats["ma10"]:
            score += 4
        if stats["ma10"] >= stats["ma20"]:
            score += 4
        if stats["ma20"] >= stats["ma60"]:
            score += 4

    # 2. 이평선 기울기
    if stats["ma20_slope"] > 0:
        score += 10
    if stats["ma60_slope"] > 0:
        score += 10

    # 3. 상대강도
    rs20 = stats["chg20d"] - market_stats.get("chg20d", 0)
    rs60 = stats["chg60d"] - market_stats.get("chg60d", 0)

    if rs20 > 0:
        score += 10
    if rs20 > 5:
        score += 5
    if rs60 > 0:
        score += 10
    if rs60 > 10:
        score += 5

    # 4. 거래량
    if stats["vol_ratio"] >= 2.0:
        score += 10
    elif stats["vol_ratio"] >= 1.5:
        score += 6
    elif stats["vol_ratio"] <= 0.7:
        score -= 3

    # 5. 이격도 과열 감점
    dist = stats["dist_ma20"]

    if 0 <= dist <= 12:
        score += 8
    elif 12 < dist <= 20:
        score += 2
    elif dist > 20:
        score -= 8
    elif dist < 0:
        score -= 8

    # 6. 이벤트
    if stats["cross20_up"]:
        score += 8
    if stats["cross20_down"]:
        score -= 15
    if stats["cross60_down"]:
        score -= 30

    return score, rs20, rs60


def grade_from_score(score):
    if score >= 75:
        return "A"
    if score >= 60:
        return "B+"
    if score >= 45:
        return "B"
    if score >= 30:
        return "C"
    return "D"


def decision_from_stats(stats, score):
    if stats["cross60_down"]:
        return "전량 매도 검토"

    if stats["cross20_down"]:
        return "30% 매도 검토"

    if score >= 75:
        if stats["dist_ma20"] > 20:
            return "보유 유지 / 신규매수 주의"
        return "비중 확대 후보"

    if score >= 60:
        if stats["dist_ma20"] > 20:
            return "보유 유지 / 추격매수 주의"
        return "보유 유지 / 분할매수 후보"

    if score >= 45:
        return "관망 후보"

    if score >= 30:
        return "비중 축소 후보"

    return "약세 / 매수 제외"


def overheat_msg(dist_ma20):
    if dist_ma20 > 25:
        return f"20일선 대비 +{dist_ma20:.1f}% → 과열 강함"
    if dist_ma20 > 20:
        return f"20일선 대비 +{dist_ma20:.1f}% → 과열 주의"
    if dist_ma20 > 12:
        return f"20일선 대비 +{dist_ma20:.1f}% → 다소 높음"
    if dist_ma20 >= 0:
        return f"20일선 대비 +{dist_ma20:.1f}% → 적정"
    return f"20일선 대비 {dist_ma20:.1f}% → 20일선 아래"


# =========================
# 시장 판단
# =========================

def fetch_market_stats():
    markets = {}

    for key, ticker in MARKET_INDEX.items():
        stats = fetch_stats(ticker)

        if stats is None:
            continue

        markets[key] = stats

    return markets


def market_status_text(markets):
    lines = ["💰 전체 주식 비중 가이드", ""]

    valid = []

    for key in ["kr", "us", "semi"]:
        if key not in markets:
            continue

        m = markets[key]
        valid.append(m)

        lines.append(
            f"- {MARKET_NAME[key]}: "
            f"20일선 {'위' if m['above20'] else '아래'} / "
            f"60일선 {'위' if m['above60'] else '아래'} / "
            f"20D {fmt_pct_dot(m['chg20d'])} / "
            f"60D {fmt_pct_dot(m['chg60d'])}"
        )

    if not valid:
        lines.append("시장 데이터 없음")
        lines.append("")
        return lines, "데이터 부족", 30, 60

    above20_count = sum(1 for m in valid if m["above20"])
    above60_count = sum(1 for m in valid if m["above60"])
    aligned_count = sum(1 for m in valid if m["is_aligned"])

    score = above20_count + above60_count + aligned_count

    lines.append("")

    if score >= 8:
        market_status = "공격 가능"
        min_weight, max_weight = 70, 100
        comment = "지수와 반도체가 대부분 20/60일선 위에 있음. 주도주 중심 비중 확대 가능."
    elif score >= 6:
        market_status = "양호"
        min_weight, max_weight = 60, 90
        comment = "시장 추세는 양호. 다만 과열 종목은 추격보다 눌림 확인."
    elif score >= 4:
        market_status = "중립"
        min_weight, max_weight = 40, 70
        comment = "시장 추세가 애매함. 정배열 강한 종목 위주로만 선별."
    elif score >= 2:
        market_status = "방어"
        min_weight, max_weight = 20, 50
        comment = "지수 추세가 약함. 신규매수보다 20/60일선 이탈 관리 우선."
    else:
        market_status = "위험"
        min_weight, max_weight = 0, 30
        comment = "시장 대부분이 약세. 현금비중 확대와 손절 기준 준수 우선."

    lines.append(f"시장판단: {market_status}")
    lines.append(f"권장 주식 비중 구간: {min_weight}~{max_weight}%")
    lines.append(f"해석: {comment}")
    lines.append("")

    return lines, market_status, min_weight, max_weight


# =========================
# 출력 포맷
# =========================

def fmt_pct_dot(x: float) -> str:
    if x > 0:
        return f"🟢{x:+.2f}%"
    elif x < 0:
        return f"🔴{x:+.2f}%"
    else:
        return f"{x:+.2f}%"


def ma_flag(close: float, ma: float) -> str:
    return "🟢▲" if close >= ma else "🔴▼"


def vol_badge(vol_ratio: float) -> str:
    if vol_ratio >= 2.0:
        return "🔥"
    if vol_ratio >= 1.5:
        return "⚡"
    if vol_ratio <= 0.7:
        return "💧"
    return ""


def format_price(ticker, price):
    if ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return f"{price:,.0f}원"
    return f"${price:,.2f}"


def trend_msg(stats):
    if stats["is_aligned"] and stats["ma20_slope"] > 0 and stats["ma60_slope"] > 0:
        return "완전 정배열 + 20/60일선 상승"

    if stats["is_aligned"]:
        return "완전 정배열"

    if stats["above20"] and stats["above60"] and stats["ma20"] >= stats["ma60"]:
        return "중기 상승 구조"

    if stats["above20"] and not stats["above60"]:
        return "단기 반등"

    if not stats["above20"] and stats["above60"]:
        return "중기선 위 조정"

    return "약세 또는 정배열 아님"


def format_block(r):
    ticker = r["ticker"]
    name = TICKER_NAME_MAP.get(ticker, ticker)

    signal = []

    if r["cross60_down"]:
        signal.append("🚨60이탈")
    if r["cross20_down"]:
        signal.append("⚠️20이탈")
    if r["cross20_up"] and r["vol_ratio"] >= 2.0:
        signal.append("🚀20돌파")
    elif r["cross20_up"]:
        signal.append("⭐20돌파")

    signal_text = " ".join(signal)
    display_name = f"{signal_text} {name} ({ticker})".strip()

    return (
        f"{display_name}\n"
        f"판단: {r['decision']}\n"
        f"등급: {r['grade']} / 점수: {r['score']:.0f}점\n"
        f"추세: {trend_msg(r)}\n"
        f"상대강도: {r['market_name']} 대비 20D {r['rs20']:+.2f}%p / 60D {r['rs60']:+.2f}%p\n"
        f"과열도: {overheat_msg(r['dist_ma20'])}\n"
        f"이평선 기울기: 20일 {r['ma20_slope']:+.2f}% / 60일 {r['ma60_slope']:+.2f}%\n"
        f"거래량: {r['vol_ratio']:.2f}x {vol_badge(r['vol_ratio'])}\n"
        f"\n"
        f"종가: {format_price(ticker, r['close'])}\n"
        f"전일: {fmt_pct_dot(r['chg1d'])} | 주간(5D): {fmt_pct_dot(r['chg5d'])}\n"
        f"20D: {fmt_pct_dot(r['chg20d'])} | 60D: {fmt_pct_dot(r['chg60d'])}\n"
        f"5일이평선:  {format_price(ticker, r['ma5'])} {ma_flag(r['close'], r['ma5'])}\n"
        f"10일이평선: {format_price(ticker, r['ma10'])} {ma_flag(r['close'], r['ma10'])}\n"
        f"20일이평선: {format_price(ticker, r['ma20'])} {ma_flag(r['close'], r['ma20'])}\n"
        f"60일이평선: {format_price(ticker, r['ma60'])} {ma_flag(r['close'], r['ma60'])}\n"
    )


# =========================
# 섹션 구성
# =========================

def build_section_lines(title: str, tickers: list[str], markets: dict):
    lines = [title]
    results = []
    missing = []

    event_list = {
        "cross20_up": [],
        "cross20_up_volume": [],
        "cross20_down": [],
        "cross60_down": [],
        "strong_buy": [],
        "overheated": [],
    }

    for t in tickers:
        stats = fetch_stats(t)

        if stats is None:
            missing.append(t)
            continue

        market_key = get_market_key(t)
        market_stats = markets.get(market_key)

        if market_stats is None:
            market_stats = {
                "chg20d": 0,
                "chg60d": 0,
            }

        score, rs20, rs60 = calc_stock_score(stats, market_stats)

        grade = grade_from_score(score)
        decision = decision_from_stats(stats, score)
        market_name = MARKET_NAME.get(market_key, "시장")

        stats["score"] = score
        stats["rs20"] = rs20
        stats["rs60"] = rs60
        stats["grade"] = grade
        stats["decision"] = decision
        stats["market_key"] = market_key
        stats["market_name"] = market_name

        name = TICKER_NAME_MAP.get(t, t)

        if stats["cross20_up"]:
            if stats["vol_ratio"] >= 2.0:
                event_list["cross20_up_volume"].append(
                    f"- {name} ({t}) | 매수 적극 검토 | 거래량 {stats['vol_ratio']:.2f}x / 점수 {score:.0f}"
                )
            else:
                event_list["cross20_up"].append(
                    f"- {name} ({t}) | 매수 고려 | 점수 {score:.0f}"
                )

        if stats["cross20_down"]:
            event_list["cross20_down"].append(
                f"- {name} ({t}) | 30% 매도 검토 | 점수 {score:.0f}"
            )

        if stats["cross60_down"]:
            event_list["cross60_down"].append(
                f"- {name} ({t}) | 전량 매도 검토 | 점수 {score:.0f}"
            )

        if score >= 75 and stats["dist_ma20"] <= 20:
            event_list["strong_buy"].append(
                f"- {name} ({t}) | 비중 확대 후보 | 등급 {grade} / 점수 {score:.0f}"
            )

        if stats["dist_ma20"] > 20 and score >= 60:
            event_list["overheated"].append(
                f"- {name} ({t}) | 주도주지만 과열 주의 | 20일선 대비 +{stats['dist_ma20']:.1f}%"
            )

        results.append(stats)

    # 정렬 기준
    # 점수 높은 순 → 정배열 → 상대강도 → 20일 기울기 → 거래량
    results.sort(
        key=lambda x: (
            x["score"],
            x["is_aligned"],
            x["rs20"],
            x["rs60"],
            x["ma20_slope"],
            x["vol_ratio"],
        ),
        reverse=True
    )

    # 상단 / 중간 / 하단 분리
    upper = [r for r in results if r["score"] >= 60]
    middle = [r for r in results if 40 <= r["score"] < 60]
    lower = [r for r in results if r["score"] < 40]

    if upper:
        lines.append("")
        lines.append("🟢 상단: 비중 확대 / 보유 우선 후보")
        lines.append("")
        for r in upper:
            lines.append(format_block(r))

    if middle:
        lines.append("")
        lines.append("🟡 중간: 관망 후보")
        lines.append("")
        for r in middle:
            lines.append(format_block(r))

    if lower:
        lines.append("")
        lines.append("🔴 하단: 비중 축소 / 매수 제외 후보")
        lines.append("")
        for r in lower:
            lines.append(format_block(r))

    if missing:
        lines.append("")
        lines.append("⚠️ 데이터 없음/기간 부족")
        for t in missing:
            lines.append(f"- {t}")

    lines.append("")

    return lines, event_list


# =========================
# 메일 발송
# =========================

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


# =========================
# 메인
# =========================

def main():
    now_kst = datetime.utcnow() + timedelta(hours=9)
    today = now_kst.strftime("%m/%d %H:%M")

    header = f"📈 주도주 추세추종 리포트 | {today}"

    lines = [header, ""]

    # 시장 데이터
    markets = fetch_market_stats()
    market_lines, market_status, min_weight, max_weight = market_status_text(markets)
    lines += market_lines

    all_events = {
        "cross20_up": [],
        "cross20_up_volume": [],
        "cross20_down": [],
        "cross60_down": [],
        "strong_buy": [],
        "overheated": [],
    }

    body_lines = []

    section_lines, events = build_section_lines("📦 PORTFOLIO - 🇰🇷 KOREA", TICKERS_KR, markets)
    body_lines += section_lines
    for key in all_events:
        all_events[key] += events[key]

    section_lines, events = build_section_lines("📦 PORTFOLIO - 🇺🇸 USA", TICKERS_US, markets)
    body_lines += section_lines
    for key in all_events:
        all_events[key] += events[key]

    section_lines, events = build_section_lines("👀 WATCHLIST - 🇰🇷 KOREA", WATCHLIST_KR, markets)
    body_lines += section_lines
    for key in all_events:
        all_events[key] += events[key]

    section_lines, events = build_section_lines("👀 WATCHLIST - 🇺🇸 USA", WATCHLIST_US, markets)
    body_lines += section_lines
    for key in all_events:
        all_events[key] += events[key]

    summary = ["📌 오늘 주요 이벤트", ""]

    has_event = any(len(v) > 0 for v in all_events.values())

    if not has_event:
        summary.append("오늘 주요 이벤트 없음")
        summary.append("")
    else:
        if all_events["strong_buy"]:
            summary.append("🟢 비중 확대 후보")
            summary += all_events["strong_buy"]
            summary.append("")

        if all_events["cross20_up_volume"]:
            summary.append("🚀 20일선 상향돌파 + 거래량")
            summary += all_events["cross20_up_volume"]
            summary.append("")

        if all_events["cross20_up"]:
            summary.append("⭐ 20일선 상향돌파")
            summary += all_events["cross20_up"]
            summary.append("")

        if all_events["overheated"]:
            summary.append("🔥 주도주 과열 주의")
            summary += all_events["overheated"]
            summary.append("")

        if all_events["cross20_down"]:
            summary.append("⚠️ 20일선 하향이탈")
            summary += all_events["cross20_down"]
            summary.append("")

        if all_events["cross60_down"]:
            summary.append("🚨 60일선 하향이탈")
            summary += all_events["cross60_down"]
            summary.append("")

    guide = [
        "📊 전략/정렬 기준",
        "전략: GDP·산업 성장을 이끄는 주도주 중심 추세추종",
        "주식 비중: 주도주 존재 + 상승 추세 확인 시 확대, 주도주 부재/추세 훼손 시 축소",
        "",
        "📈 종목 해석 기준",
        "A: 강한 주도주 후보 / 비중 확대 가능",
        "B+: 보유 유지 또는 분할매수 후보",
        "B: 관망 또는 소액 접근",
        "C: 약한 흐름 / 우선순위 낮음",
        "D: 매수 제외 또는 비중 축소 후보",
        "",
        "상단 = 비중 확대 / 보유 우선 후보",
        "중간 = 관망 후보",
        "하단 = 비중 축소 / 매수 제외 후보",
        "",
        "20일선 하향이탈 = 일부 매도 검토",
        "60일선 하향이탈 = 강한 매도 검토",
        "20일선 상향돌파 = 재매수/추가매수 후보",
        "",
        "정렬: 점수 → 정배열 → 상대강도 → 이평선 기울기 → 거래량",
        "",
    ]

    lines = lines + summary + guide + body_lines

    message = "\n".join(lines)

    print("\n" + message + "\n" + "-" * 40)
    send_to_email(message)


if __name__ == "__main__":
    main()
