import html
import logging
import platform
import re
import subprocess
import time
from datetime import datetime, time as dt_time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None


# ── APP CONFIG ─────────────────────────────────────────────────────
st.set_page_config(page_title="Breakout Screener", page_icon="📈", layout="wide")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("breakout_screener")

MARKET_TZ = ZoneInfo("America/New_York")
CHANNEL_BARS = 14
REQUEST_DELAY_SEC = 0.05
NASDAQ_TIMEOUT_SEC = 20
DATA_TIMEOUT_SEC = 12
AI_TIMEOUT_SEC = 120


def secret_or_default(name: str, default: str = "") -> str:
    """Read Streamlit secret if present, otherwise keep the local fallback."""
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = default
    return str(value or default)


# ── TELEGRAM CONFIG ────────────────────────────────────────────────
# Kept as local fallbacks by user request. Prefer st.secrets when configured.
TELEGRAM_TOKEN = secret_or_default("TELEGRAM_TOKEN", "8561990969:AAGrJ4Mc6hH1mmpVT_pNqfNt7sIz1mONgv4")
TELEGRAM_CHAT_ID = secret_or_default("TELEGRAM_CHAT_ID", "716517029")


# ── ALPACA CONFIG ─────────────────────────────────────────────────
# Kept as local fallbacks by user request. Prefer st.secrets when configured.
ALPACA_KEY = secret_or_default("ALPACA_KEY", "PKJU45FE3EI27THY3Z6MSNXEVP")
ALPACA_SECRET = secret_or_default("ALPACA_SECRET", "GF4UUuyVq1tRuXsn2S4WL66Vh3BrjfeDighy1gVfuhkP")
ALPACA_BASE = "https://data.alpaca.markets"
ALPACA_HEADERS = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET,
}


# ── ANTHROPIC CONFIG ──────────────────────────────────────────────
ANTHROPIC_API_KEY = secret_or_default("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = secret_or_default("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


# ── HELPERS ───────────────────────────────────────────────────────
def now_et() -> datetime:
    return datetime.now(MARKET_TZ)


def now_et_str(fmt: str = "%H:%M:%S ET") -> str:
    return now_et().strftime(fmt)


def parse_price(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).replace("$", "").replace(",", "").strip()
    if not text or text.upper() in {"N/A", "NA", "NONE", "-"}:
        return None
    try:
        price = float(text)
    except ValueError:
        return None
    return price if price > 0 else None


def normalize_symbol(symbol: str, name: str = "") -> str | None:
    sym = (symbol or "").strip().upper()
    if not sym:
        return None

    # Common-stock universe: keep normal letter-only tickers, filter funds/derivatives by name.
    if not re.fullmatch(r"[A-Z]{1,5}", sym):
        return None

    name_l = (name or "").lower()
    excluded_name_pattern = (
        r"\b("
        r"etf|fund|closed[- ]end|exchange traded|trust|"
        r"warrant|warrants|right|rights|unit|units|"
        r"preferred|preference|depositary|depository|"
        r"note|notes|etn|baby bond|debenture"
        r")\b"
    )
    if re.search(excluded_name_pattern, name_l):
        return None
    return sym


def normalize_ohlcv(df: pd.DataFrame | None, source: str) -> pd.DataFrame | None:
    if df is None or df.empty:
        return None

    data = df.copy()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    rename_map = {
        "o": "Open",
        "h": "High",
        "l": "Low",
        "c": "Close",
        "v": "Volume",
        "t": "Date",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }
    data.rename(columns={col: rename_map.get(str(col), col) for col in data.columns}, inplace=True)

    if "Date" in data.columns:
        data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
        data.set_index("Date", inplace=True)

    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [col for col in required if col not in data.columns]
    if missing:
        LOGGER.warning("Source %s is missing columns: %s", source, ", ".join(missing))
        return None

    data = data[required].copy()
    for col in required:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    data = data.dropna(subset=required).sort_index()
    data = data[(data["Open"] > 0) & (data["High"] > 0) & (data["Low"] > 0) & (data["Close"] > 0)]
    if data.empty:
        return None
    data.attrs["source"] = source
    return data


def to_market_tz(index: pd.Index) -> pd.DatetimeIndex:
    dt_index = pd.DatetimeIndex(pd.to_datetime(index, errors="coerce"))
    dt_index = dt_index[~pd.isna(dt_index)]
    if dt_index.tz is None:
        return dt_index.tz_localize(MARKET_TZ)
    return dt_index.tz_convert(MARKET_TZ)


def get_market_status() -> tuple[str, str]:
    current = now_et()
    minute = current.hour * 60 + current.minute
    if 4 * 60 <= minute < 9 * 60 + 30:
        return "info", "🌅 Pre-Market активен (4:00–9:30 ET)"
    if 9 * 60 + 30 <= minute <= 16 * 60:
        return "success", "🟢 Основная сессия открыта (9:30–16:00 ET)"
    if 16 * 60 < minute <= 20 * 60:
        return "info", "🌙 Post-Market активен (16:00–20:00 ET)"
    return "warning", "💤 Рынок закрыт"


def result_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("Тикер", "")), str(row.get("Сигнал", "")), str(row.get("Сессия", "")))


def merge_results(new_rows: list[dict[str, Any]], old_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in old_rows:
        merged[result_key(row)] = row
    for row in new_rows:
        merged[result_key(row)] = row
    return sorted(
        merged.values(),
        key=lambda row: (int(row.get("Тех.балл", 0)), float(row.get("Объём ×", 0))),
        reverse=True,
    )


def remember_error(message: str) -> None:
    errors = st.session_state.setdefault("scan_errors", [])
    errors.append(f"{now_et_str()} · {message}")
    del errors[:-12]


# ── DATA SOURCES ──────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_tickers(exchange: str = "ALL", max_price_up: float = 10.0, max_price_dn: float = 100.0) -> list[dict[str, Any]]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://www.nasdaq.com/",
    }
    exchanges = ["nasdaq", "nyse", "amex"] if exchange == "ALL" else [exchange.lower()]
    max_price_global = max(float(max_price_up), float(max_price_dn))
    tickers: list[dict[str, Any]] = []
    seen: set[str] = set()

    for ex in exchanges:
        try:
            resp = requests.get(
                "https://api.nasdaq.com/api/screener/stocks",
                params={"tableonly": "true", "limit": 10000, "exchange": ex},
                headers=headers,
                timeout=NASDAQ_TIMEOUT_SEC,
            )
            resp.raise_for_status()
            rows = resp.json().get("data", {}).get("table", {}).get("rows", []) or []
        except Exception as exc:
            LOGGER.warning("Could not load tickers from Nasdaq %s: %s", ex, exc)
            continue

        for row in rows:
            name = row.get("name", "") or ""
            sym = normalize_symbol(row.get("symbol", ""), name)
            if not sym or sym in seen:
                continue

            price = parse_price(row.get("lastsale"))
            if price is None or price > max_price_global:
                continue

            seen.add(sym)
            tickers.append(
                {
                    "ticker": sym,
                    "exchange": ex.upper(),
                    "name": name,
                    "price_api": price,
                }
            )

    if len(tickers) >= 50:
        return tickers

    LOGGER.warning("Nasdaq returned too few tickers; using fallback list.")
    fallback = [
        "SNDL", "GNUS", "CTRM", "HCDI", "EXPR", "CLPS", "SENS", "VERB",
        "ATER", "IMPP", "SHIP", "GOVX", "BIVI", "QNRX", "HYMC", "CLNN",
        "BOXL", "FFIE", "MARK", "WISA", "GLYC", "BNGO", "NKLA", "BLNK",
        "GOEV", "WKHS", "SOLO", "CLOV", "WISH", "MVIS", "OPEN", "SOFI",
        "PLUG", "RIVN", "LCID", "MARA", "RIOT", "BITF", "HIMS", "DNA",
    ]
    return [{"ticker": t, "exchange": "US", "name": "", "price_api": 0.0} for t in fallback]


@st.cache_data(ttl=60, show_spinner=False)
def fetch_alpaca_bars(ticker: str, days: int = 45) -> pd.DataFrame | None:
    if not ALPACA_KEY or not ALPACA_SECRET:
        return None

    end = now_et().date()
    start = end - timedelta(days=days + 10)
    try:
        resp = requests.get(
            f"{ALPACA_BASE}/v2/stocks/{ticker}/bars",
            headers=ALPACA_HEADERS,
            params={
                "timeframe": "1Day",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "limit": 80,
                "feed": "iex",
                "adjustment": "raw",
            },
            timeout=DATA_TIMEOUT_SEC,
        )
        if resp.status_code in {401, 403}:
            LOGGER.warning("Alpaca auth failed for %s: %s", ticker, resp.status_code)
            return None
        resp.raise_for_status()
        bars = resp.json().get("bars", [])
    except Exception as exc:
        LOGGER.info("Alpaca failed for %s: %s", ticker, exc)
        return None

    if len(bars) < CHANNEL_BARS + 2:
        return None
    return normalize_ohlcv(pd.DataFrame(bars), "Alpaca")


@st.cache_data(ttl=60, show_spinner=False)
def fetch_yahoo_daily(ticker: str) -> pd.DataFrame | None:
    if yf is None:
        LOGGER.warning("yfinance is not installed; Yahoo daily fallback is disabled.")
        return None

    try:
        df = yf.download(
            ticker,
            period="60d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
            timeout=DATA_TIMEOUT_SEC,
        )
    except Exception as exc:
        LOGGER.info("Yahoo daily failed for %s: %s", ticker, exc)
        return None
    return normalize_ohlcv(df, "Yahoo daily")


@st.cache_data(ttl=45, show_spinner=False)
def fetch_yahoo_intraday(ticker: str, session: str) -> pd.DataFrame | None:
    if yf is None:
        LOGGER.warning("yfinance is not installed; intraday sessions are disabled.")
        return None

    try:
        df = yf.download(
            ticker,
            period="5d",
            interval="1m",
            auto_adjust=True,
            prepost=True,
            progress=False,
            threads=False,
            timeout=DATA_TIMEOUT_SEC,
        )
    except Exception as exc:
        LOGGER.info("Yahoo intraday failed for %s: %s", ticker, exc)
        return None

    df = normalize_ohlcv(df, "Yahoo intraday")
    if df is None or len(df) < 10:
        return None

    try:
        df.index = to_market_tz(df.index)
    except Exception as exc:
        LOGGER.info("Could not convert timezone for %s: %s", ticker, exc)
        return None

    if session == "premarket":
        df = df[(df.index.time >= dt_time(4, 0)) & (df.index.time < dt_time(9, 30))]
    elif session == "postmarket":
        df = df[(df.index.time > dt_time(16, 0)) & (df.index.time <= dt_time(20, 0))]
    else:
        return None

    if len(df) < CHANNEL_BARS + 2:
        return None

    resampled = (
        df.resample("5min")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
        .dropna()
    )
    resampled.attrs["source"] = f"Yahoo {session}"
    return resampled if len(resampled) >= CHANNEL_BARS + 2 else None


def fetch_history(ticker: str, session: str = "regular") -> pd.DataFrame | None:
    if session == "regular":
        alpaca = fetch_alpaca_bars(ticker)
        if alpaca is not None and len(alpaca) >= CHANNEL_BARS + 2:
            return alpaca
        return fetch_yahoo_daily(ticker)
    return fetch_yahoo_intraday(ticker, session)


@st.cache_data(ttl=12 * 3600, show_spinner=False)
def has_options(ticker: str) -> bool:
    if yf is None:
        return False

    try:
        return len(yf.Ticker(ticker).options) > 0
    except Exception as exc:
        LOGGER.info("Could not check options for %s: %s", ticker, exc)
        return False


# ── SCANNER LOGIC ─────────────────────────────────────────────────
def tech_score_fn(sig: str, channel_width: float, vol_mult: float, body_pct: float) -> int:
    score = 0
    if "↑" in sig or "↓" in sig:
        score += 5
    elif "🔥" in sig:
        score += 3

    if channel_width <= 5:
        score += 4
    elif channel_width <= 8:
        score += 3
    elif channel_width <= 12:
        score += 2
    elif channel_width <= 16:
        score += 1

    if vol_mult >= 7:
        score += 4
    elif vol_mult >= 5:
        score += 3
    elif vol_mult >= 3:
        score += 2
    elif vol_mult >= 2:
        score += 1

    if body_pct >= 8:
        score += 2
    elif body_pct >= 3:
        score += 1
    return score


def check_no_gaps(opens: pd.Series, closes: pd.Series, start_idx: int, latest_idx: int, max_gap_pct: float) -> bool:
    if start_idx < 1 or latest_idx <= start_idx:
        return False

    for idx in range(start_idx, latest_idx + 1):
        prev_close = float(closes.iloc[idx - 1])
        curr_open = float(opens.iloc[idx])
        if prev_close <= 0 or curr_open <= 0:
            return False
        gap_pct = abs(curr_open - prev_close) / prev_close * 100
        if gap_pct > max_gap_pct:
            return False
    return True


def analyze(ticker_info: dict[str, Any], cfg: dict[str, Any], session: str = "regular") -> dict[str, Any] | None:
    ticker = ticker_info["ticker"]
    df = fetch_history(ticker, session)
    if df is None or len(df) < cfg["channel_bars"] + 2:
        return None

    opens = df["Open"].astype(float).squeeze()
    highs = df["High"].astype(float).squeeze()
    lows = df["Low"].astype(float).squeeze()
    closes = df["Close"].astype(float).squeeze()
    volumes = df["Volume"].astype(float).squeeze()

    n = len(df)
    latest_idx = n - 1
    channel_end = n - 2
    channel_start = channel_end - cfg["channel_bars"] + 1
    if channel_start < 1:
        return None

    last_price = float(closes.iloc[latest_idx])
    last_vol = float(volumes.iloc[latest_idx])
    today_open = float(opens.iloc[latest_idx])
    if last_price <= 0 or last_vol <= 0 or today_open <= 0:
        return None

    channel_high = float(highs.iloc[channel_start : channel_end + 1].max())
    channel_low = float(lows.iloc[channel_start : channel_end + 1].min())
    if channel_high <= 0 or channel_low <= 0 or channel_high <= channel_low:
        return None

    channel_width = (channel_high - channel_low) / channel_low * 100
    if channel_width > cfg["channel_pct"]:
        return None

    if cfg["no_gaps"] and not check_no_gaps(
        opens,
        closes,
        channel_start,
        latest_idx,
        cfg["max_gap_pct"],
    ):
        return None

    body_pct = abs(last_price - today_open) / today_open * 100
    breakout_pct = (last_price - channel_high) / channel_high * 100
    breakdown_pct = (channel_low - last_price) / channel_low * 100

    sig_type: str | None = None
    change_pct = 0.0
    if breakout_pct >= cfg["min_breakout"]:
        sig_type = "BREAKOUT ↑"
        change_pct = round(breakout_pct, 1)
    elif breakdown_pct >= cfg["min_breakout"]:
        sig_type = "BREAKDOWN ↓"
        change_pct = round(breakdown_pct, 1)

    channel_vols = volumes.iloc[channel_start : channel_end + 1]
    channel_vols = channel_vols[channel_vols > 0]
    if len(channel_vols) < max(5, cfg["channel_bars"] // 2):
        return None

    max_vol = float(channel_vols.max())
    avg_vol = float(channel_vols.mean())
    vol_mult = last_vol / max_vol if max_vol > 0 else 0.0
    if vol_mult < cfg["min_vol"]:
        return None

    if sig_type is None:
        sig_type = "ОБЪЁМ 🔥"

    if cfg["signal_type"] != "ALL" and cfg["signal_type"] != sig_type:
        return None
    if sig_type == "BREAKOUT ↑" and last_price > cfg["max_price_up"]:
        return None
    if sig_type == "BREAKDOWN ↓" and last_price > cfg["max_price_dn"]:
        return None
    if sig_type == "ОБЪЁМ 🔥" and last_price > max(cfg["max_price_up"], cfg["max_price_dn"]):
        return None
    if cfg["options_only"] and not has_options(ticker):
        return None
    if cfg["strict"] and body_pct < cfg["min_body_pct"]:
        return None

    pct_display = "—"
    if sig_type == "BREAKOUT ↑":
        pct_display = f"+{change_pct}%"
    elif sig_type == "BREAKDOWN ↓":
        pct_display = f"-{change_pct}%"

    return {
        "Тикер": ticker,
        "Название": (ticker_info.get("name") or "")[:32],
        "Биржа": ticker_info.get("exchange", ""),
        "Цена $": round(last_price, 4),
        "Сигнал": sig_type,
        "Пробой %": pct_display,
        "Объём ×": round(vol_mult, 1),
        "Объём ср.": int(avg_vol),
        "Ширина канала": f"{round(channel_width, 1)}%",
        "Канал": f"${round(channel_low, 4)}–${round(channel_high, 4)}",
        "Тело свечи %": round(body_pct, 1),
        "Опционы": "✅" if has_options(ticker) else "—",
        "Тех.балл": tech_score_fn(sig_type, channel_width, vol_mult, body_pct),
        "Сессия": session.upper(),
        "Источник": df.attrs.get("source", ""),
        "Время": now_et_str(),
    }


# ── NOTIFICATIONS ─────────────────────────────────────────────────
def send_telegram(message: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        LOGGER.warning("Telegram is not configured.")
        return False

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
        if resp.status_code != 200:
            LOGGER.warning("Telegram failed: %s %s", resp.status_code, resp.text[:300])
            return False
        return True
    except Exception as exc:
        LOGGER.warning("Telegram request failed: %s", exc)
        return False


def telegram_signal_message(row: dict[str, Any]) -> str:
    icon = "🟢" if "↑" in row["Сигнал"] else ("🔴" if "↓" in row["Сигнал"] else "🔥")
    ticker = html.escape(str(row["Тикер"]))
    signal = html.escape(str(row["Сигнал"]))
    return (
        f"📈 <b>СИГНАЛ НАЙДЕН!</b>\n"
        f"{icon} <b>{ticker}</b>  ${row['Цена $']}\n"
        f"Сигнал: {signal}  {row['Пробой %']}\n"
        f"Объём ×{row['Объём ×']}  | Канал: {row['Ширина канала']}\n"
        f"Сессия: {row['Сессия']} | Балл: {row['Тех.балл']}\n"
        f"⏰ {now_et_str('%H:%M ET')}"
    )


def should_notify(row: dict[str, Any]) -> bool:
    notified = st.session_state.setdefault("notified_signals", set())
    key = f"{now_et().date().isoformat()}:{row['Тикер']}:{row['Сигнал']}:{row['Сессия']}"
    if key in notified:
        return False
    notified.add(key)
    return True


def play_sound() -> None:
    if platform.system() != "Darwin":
        return
    try:
        subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], timeout=3, check=False)
    except Exception as exc:
        LOGGER.info("Could not play sound: %s", exc)


# ── AI ANALYSIS ───────────────────────────────────────────────────
def build_ai_prompt(hits: list[dict[str, Any]]) -> str:
    tickers_str = ", ".join(row["Тикер"] for row in hits)
    details = "\n".join(
        (
            f"- {row['Тикер']}: цена ${row['Цена $']}, сигнал {row['Сигнал']}, "
            f"объём ×{row['Объём ×']}, канал {row['Канал']}, ширина {row['Ширина канала']}, "
            f"тело свечи {row['Тело свечи %']}%, тех.балл {row['Тех.балл']}, "
            f"сессия {row['Сессия']}, источник данных {row.get('Источник', '')}"
        )
        for row in hits
    )
    return f"""Ты опытный трейдер, скальпер и финансовый аналитик.
Дата анализа: {now_et().strftime('%Y-%m-%d %H:%M ET')}.
Скринер нашёл следующие акции с паттерном пробоя/объёма: {tickers_str}

Данные по акциям:
{details}

Сделай полный прикладной разбор на русском языке. Работай строго по методике:

1. Для каждого тикера проверь свежий новостной фон через web_search:
   - приоритет: новости за последние 72 часа, затем 7 дней, затем 30 дней;
   - источники: company investor relations/press release, SEC/8-K/S-1, Nasdaq/NYSE notices,
     FDA/clinical updates для biotech, PRNewswire/BusinessWire/GlobeNewswire, Reuters/Benzinga/MarketWatch/Yahoo Finance;
   - для каждой важной новости укажи дату, источник и почему это важно для движения цены;
   - если свежих подтверждённых новостей нет, прямо напиши: "свежий катализатор не найден".
2. Оцени техническую картину: качество канала, сила пробоя/пролива, объём, тело свечи,
   близкие уровни поддержки/сопротивления, риск ложного пробоя.
3. Оцени риск: ликвидность, новостной шум, penny-stock риск, dilution/offering, reverse split,
   FDA/clinical risk, earnings risk, short squeeze risk, gap risk.
4. Оцени рыночный интерес: если доступны публичные данные/новости/соцсигналы, укажи их; не выдумывай.

Используй шкалу 0-100:
- Техника: 40 баллов
- Объём/ликвидность: 20 баллов
- Новости/катализаторы: 25 баллов
- Риск-контроль: 15 баллов, где высокий балл = риск ниже/лучше контролируется

Обязательный формат ответа:

## 🏆 TOP-3 SETUPS
### #1 🟢 TICKER — итоговый балл XX/100
- Почему #1:
- Техника:
- Новости/катализаторы с датами и источниками:
- Настроение/интерес рынка:
- План сделки: вход/зона наблюдения, цель, invalidation/stop:
- Главные риски:

### #2 🟡 TICKER — итоговый балл XX/100
- Почему #2:
- Техника:
- Новости/катализаторы с датами и источниками:
- Настроение/интерес рынка:
- План сделки: вход/зона наблюдения, цель, invalidation/stop:
- Главные риски:

### #3 🔴 TICKER — итоговый балл XX/100
- Почему #3:
- Техника:
- Новости/катализаторы с датами и источниками:
- Настроение/интерес рынка:
- План сделки: вход/зона наблюдения, цель, invalidation/stop:
- Главные риски:

## ⚪ NEWS WINNER
### ⚪ TICKER — сила новостей XX/25
- Лучшая новость:
- Дата и источник:
- Почему это сильнее остальных:
- Насколько новость уже могла быть отыграна:
- Риск новости:

## 📊 SCORECARD
Сделай markdown-таблицу по всем проанализированным тикерам:
| Тикер | Итог | Техника/40 | Объём/20 | Новости/25 | Риск/15 | Свежая новость | Краткий вывод |

Правила:
- TOP-3 должен идти от лучшего к более слабому: #1 лучший, #2 второй, #3 третий.
- ⚪ NEWS WINNER выбирай отдельно по силе новостного фона; он может совпадать с TOP-3 или быть другим тикером.
- Не называй это персональной финансовой рекомендацией.
- Не придумывай источники, даты, новости, соцсигналы или целевые цены."""


def request_ai_analysis(hits: list[dict[str, Any]]) -> str:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY не задан. Добавь ключ в st.secrets, чтобы AI-анализ работал.")

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": ANTHROPIC_MODEL,
            "max_tokens": 4500,
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
            "messages": [{"role": "user", "content": build_ai_prompt(hits)}],
        },
        timeout=AI_TIMEOUT_SEC,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Anthropic API вернул {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    blocks = data.get("content", [])
    text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
    if not text.strip():
        raise RuntimeError("AI не вернул текстовый ответ.")
    return text.strip()


def find_marker(text: str, markers: tuple[str, ...]) -> int:
    indexes = [text.find(marker) for marker in markers if text.find(marker) >= 0]
    return min(indexes) if indexes else -1


def section_between(
    text: str,
    start_markers: tuple[str, ...],
    end_markers: tuple[str, ...],
    max_chars: int = 2000,
) -> str:
    start = find_marker(text, start_markers)
    if start < 0:
        return ""
    end_candidates = [text.find(marker, start + 1) for marker in end_markers]
    end_candidates = [idx for idx in end_candidates if idx > start]
    end = min(end_candidates) if end_candidates else min(len(text), start + max_chars)
    return text[start:end].strip()


# ── SESSION STATE ─────────────────────────────────────────────────
if "auto_last_run" not in st.session_state:
    st.session_state.auto_last_run = None
elif (
    isinstance(st.session_state.auto_last_run, datetime)
    and st.session_state.auto_last_run.tzinfo is None
):
    st.session_state.auto_last_run = st.session_state.auto_last_run.replace(tzinfo=MARKET_TZ)
if "auto_count" not in st.session_state:
    st.session_state.auto_count = 0
if "stats" not in st.session_state:
    st.session_state.stats = {"checked": 0, "up": 0, "down": 0}
if "results" not in st.session_state:
    st.session_state.results = []
if "notified_signals" not in st.session_state:
    st.session_state.notified_signals = set()
if "scan_errors" not in st.session_state:
    st.session_state.scan_errors = []


# ── SIDEBAR ───────────────────────────────────────────────────────
with st.sidebar:
    st.header("🎯 Режим поиска")
    mode = st.radio("Выбери режим:", ["🔴 СТРОГИЙ — точный паттерн", "🟡 МЯГКИЙ — больше акций"], index=0)
    strict_mode = "СТРОГИЙ" in mode

    st.divider()
    st.subheader("⚙️ Параметры")
    if strict_mode:
        default_vol, default_channel, default_breakout, default_body = 5.0, 8, 15, 3.0
        st.info("Канал 14 свечей · ширина ≤8% · объём ×5+ · пробой ≥15%")
    else:
        default_vol, default_channel, default_breakout, default_body = 2.0, 15, 5, 0.0
        st.info("Канал 14 свечей · ширина ≤15% · объём ×2+ · пробой ≥5%")

    st.divider()
    st.subheader("💲 Цена акции")
    max_price_up = st.number_input("Макс. цена BREAKOUT ↑ ($)", 0.001, 500.0, 20.0, 1.0)
    max_price_dn = st.number_input("Макс. цена BREAKDOWN ↓ ($)", 0.001, 500.0, 20.0, 1.0)

    min_vol = st.select_slider(
        "Мин. рост объёма",
        options=[2.0, 3.0, 5.0, 7.0, 10.0],
        value=default_vol,
        format_func=lambda x: f"× {x}",
    )
    channel_pct = st.slider("Ширина канала (%)", 2, 25, int(default_channel))
    min_breakout = st.slider("Мин. пробой (%)", 2, 50, int(default_breakout))

    with st.expander("Тонкие фильтры", expanded=False):
        no_gaps = st.checkbox("Фильтр гэпов", value=True)
        max_gap_pct = st.slider("Макс. гэп (%)", 2, 40, max(int(channel_pct), 8), disabled=not no_gaps)
        min_body_pct = st.slider("Мин. тело свечи в строгом режиме (%)", 0.0, 15.0, default_body, 0.5)

    st.divider()
    st.subheader("🕐 Торговая сессия")
    sess_premarket = st.checkbox("🌅 Pre-Market  (4:00–9:30 ET)", value=False)
    sess_regular = st.checkbox("📈 Дневная сессия (9:30–16:00 ET)", value=True)
    sess_postmarket = st.checkbox("🌙 Post-Market (16:00–20:00 ET)", value=False)
    if not sess_premarket and not sess_regular and not sess_postmarket:
        st.warning("Выбери хотя бы одну сессию.")

    st.divider()
    exchange = st.selectbox("Биржа", ["ALL", "NASDAQ", "NYSE", "AMEX"])
    signal_type = st.selectbox("Тип сигнала", ["ALL", "BREAKOUT ↑", "BREAKDOWN ↓", "ОБЪЁМ 🔥"], index=0)

    st.divider()
    st.subheader("🎯 Опционы")
    options_filter = st.checkbox(
        "Только акции с опционами",
        value=False,
        help="Фильтр применяется ко всем типам сигналов. Для BREAKDOWN обычно рассматривают PUT.",
    )
    if options_filter:
        st.info("Может замедлить сканирование: проверка опционов кэшируется на 12 часов.")

    max_tickers = st.slider("Акций за прогон", 50, 10000, 10000, 50)
    st.caption(
        "Фильтр рынка: только NASDAQ/NYSE/AMEX, обычные буквенные тикеры A-Z длиной до 5 символов; "
        "фонды, ETF, trust, warrants, units, preferred и notes отсекаются."
    )
    page_num = st.number_input(
        "Страница (порция акций)",
        min_value=1,
        max_value=50,
        value=1,
        step=1,
        help="Страница 1 = первые N акций, страница 2 = следующие N, и т.д.",
    )

    st.divider()
    st.subheader("⏰ Авто-сканирование")
    auto_scan = st.toggle("Включить авто-поиск", value=False)
    auto_interval = st.select_slider(
        "Интервал",
        options=[5, 10, 15, 30, 60],
        value=15,
        format_func=lambda x: f"каждые {x} мин",
        disabled=not auto_scan,
    )
    notify_sound = st.checkbox("🔔 Звук на компьютере", value=True, disabled=not auto_scan)
    if st.button("Сбросить дубли Telegram", use_container_width=True):
        st.session_state.notified_signals = set()
        st.success("Дубли уведомлений сброшены.")

    st.success("📱 Telegram подключён")
    st.caption("Данные: Alpaca IEX + Yahoo Finance fallback · время сессий: ET")


# ── AUTO REFRESH ──────────────────────────────────────────────────
if auto_scan and st_autorefresh is not None:
    st_autorefresh(interval=auto_interval * 60 * 1000, key="autorefresh_cl")
elif auto_scan and st_autorefresh is None:
    st.warning("Для авто-обновления установи пакет streamlit-autorefresh. Ручной сканер работает.")


# ── MAIN UI ───────────────────────────────────────────────────────
st.title("📈 Breakout Screener")

if yf is None:
    st.warning(
        "Пакет yfinance не установлен. Yahoo fallback, pre/post-market данные и фильтр опционов "
        "будут недоступны до установки: pip install yfinance"
    )

m1, m2, m3, m4 = st.columns(4)
m1.metric("Проверено", st.session_state.stats["checked"])
m2.metric("↑ Пробоев вверх", st.session_state.stats["up"])
m3.metric("↓ Пробоев вниз", st.session_state.stats["down"])
m4.metric("Всего найдено", len(st.session_state.results))
st.divider()

if auto_scan:
    current = now_et()
    t1, t2, t3 = st.columns(3)
    t1.info(f"⏰ Авто-поиск: каждые **{auto_interval} мин**")
    if st.session_state.auto_last_run:
        elapsed_sec = int((current - st.session_state.auto_last_run).total_seconds())
        remaining = max(0, auto_interval * 60 - elapsed_sec)
        t2.info(
            f"🕐 Последний: **{elapsed_sec // 60} мин назад** | "
            f"Следующий через: **{remaining // 60} мин {remaining % 60} сек**"
        )
        should_auto_run = elapsed_sec >= auto_interval * 60
    else:
        t2.info("🕐 Ещё не запускался — запустится сразу")
        should_auto_run = True
    t3.info(f"🔄 Прогонов: **{st.session_state.auto_count}**")

    if st.button("⏹ Пропустить текущий авто-запуск", use_container_width=False):
        st.session_state.auto_last_run = current
        should_auto_run = False
        st.rerun()
else:
    should_auto_run = False

st.divider()
btn_col, info_col = st.columns([1, 3])
with btn_col:
    start = st.button("🔍 Сканировать", type="primary", use_container_width=True)
with info_col:
    status_kind, status_text = get_market_status()
    getattr(st, status_kind)(status_text)


if start or (auto_scan and should_auto_run):
    selected_sessions = [
        session
        for session, active in [
            ("premarket", sess_premarket),
            ("regular", sess_regular),
            ("postmarket", sess_postmarket),
        ]
        if active
    ]

    if not selected_sessions:
        st.error("Нужно выбрать хотя бы одну торговую сессию.")
    else:
        cfg = {
            "max_price_up": max_price_up,
            "max_price_dn": max_price_dn,
            "channel_bars": CHANNEL_BARS,
            "min_vol": min_vol,
            "channel_pct": channel_pct,
            "min_breakout": min_breakout,
            "signal_type": signal_type,
            "strict": strict_mode,
            "min_body_pct": min_body_pct,
            "options_only": options_filter,
            "sessions": selected_sessions,
            "no_gaps": no_gaps,
            "max_gap_pct": max_gap_pct,
        }

        st.session_state.scan_errors = []
        st.session_state.stats = {"checked": 0, "up": 0, "down": 0}

        with st.spinner("Загружаем список тикеров..."):
            all_tickers = get_tickers(exchange, max_price_up, max_price_dn)

        page_start = (int(page_num) - 1) * int(max_tickers)
        page_end = page_start + int(max_tickers)
        scan_list = all_tickers[page_start:page_end]
        total_pages = max(1, (len(all_tickers) + int(max_tickers) - 1) // int(max_tickers))

        if not scan_list:
            st.warning(f"На странице {page_num} нет тикеров. Всего страниц: {total_pages}.")
        else:
            st.info(
                f"Всего тикеров: **{len(all_tickers)}** | "
                f"Страница **{page_num}/{total_pages}** | "
                f"Проверяем: **{len(scan_list)}** "
                f"(#{page_start + 1}–{min(page_end, len(all_tickers))})"
            )

            progress = st.progress(0.0)
            status = st.empty()
            table_box = st.empty()
            hits: list[dict[str, Any]] = []
            total_ops = len(scan_list) * len(selected_sessions)
            op = 0

            for session in selected_sessions:
                sess_label = {
                    "premarket": "🌅 Pre-Market",
                    "regular": "📈 Дневная",
                    "postmarket": "🌙 Post-Market",
                }[session]

                for i, ticker_info in enumerate(scan_list, start=1):
                    op += 1
                    progress.progress(min(1.0, op / total_ops))
                    status.caption(
                        f"{sess_label} | ⏳ {ticker_info['ticker']} "
                        f"({i}/{len(scan_list)}) · найдено: {len(hits)}"
                    )

                    try:
                        row = analyze(ticker_info, cfg, session)
                    except Exception as exc:
                        LOGGER.exception("Analyze failed for %s", ticker_info.get("ticker"))
                        remember_error(f"{ticker_info.get('ticker')}: {exc}")
                        row = None

                    if row:
                        hits.append(row)
                        if "↑" in row["Сигнал"]:
                            st.session_state.stats["up"] += 1
                        elif "↓" in row["Сигнал"]:
                            st.session_state.stats["down"] += 1

                        table_box.dataframe(pd.DataFrame(hits), use_container_width=True, hide_index=True)
                        if should_notify(row):
                            send_telegram(telegram_signal_message(row))

                    st.session_state.stats["checked"] = op
                    time.sleep(REQUEST_DELAY_SEC)

            st.session_state.results = merge_results(hits, st.session_state.results)
            st.session_state.auto_last_run = now_et()
            st.session_state.auto_count += 1
            progress.progress(1.0)

            if hits:
                if auto_scan and notify_sound:
                    play_sound()
                summary = (
                    f"✅ Сканирование завершено · Найдено: {len(hits)} · "
                    f"Проверено операций: {total_ops} · {now_et_str('%H:%M ET')}"
                )
                send_telegram(summary)
                st.toast("📱 Итог отправлен в Telegram", icon="✅")
                st.success(f"🚨 НАЙДЕНО {len(hits)} СИГНАЛОВ!")
            else:
                st.info("Сигналов не найдено по текущим фильтрам.")
                if auto_scan:
                    st.toast(f"Сигналов нет ({now_et_str('%H:%M ET')})")

            status.success(f"✅ Готово! Проверено операций: {total_ops} · Найдено: {len(hits)}")

            if st.session_state.scan_errors:
                with st.expander("Диагностика ошибок"):
                    st.write("\n".join(st.session_state.scan_errors))

            if hits:
                csv = pd.DataFrame(hits).to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇️ Скачать CSV",
                    data=csv,
                    file_name=f"breakout_{now_et().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                )

elif st.session_state.results:
    st.subheader(f"Последние результаты — {len(st.session_state.results)} сигналов")
    df_prev = pd.DataFrame(st.session_state.results)
    t1, t2, t3 = st.tabs(["📋 Все", "↑↓ Пробои", "🔥 Объём"])
    with t1:
        st.dataframe(df_prev, use_container_width=True, hide_index=True)
    with t2:
        st.dataframe(df_prev[df_prev["Сигнал"].str.contains("↑|↓", na=False)], use_container_width=True, hide_index=True)
    with t3:
        st.dataframe(df_prev[df_prev["Сигнал"].str.contains("🔥", na=False)], use_container_width=True, hide_index=True)

    csv = df_prev.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Скачать CSV",
        data=csv,
        file_name=f"breakout_{now_et().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )
else:
    st.info("👆 Нажми «Сканировать» для начала поиска")


# ── AI ANALYSIS UI ────────────────────────────────────────────────
if st.session_state.results:
    st.divider()
    st.subheader("🤖 AI Анализ найденных акций")
    st.caption("Информационный анализ. Не является персональной финансовой рекомендацией.")

    if st.button("🔍 Запустить AI анализ", type="secondary", use_container_width=True):
        hits_for_ai = st.session_state.results[:10]

        with st.spinner("🤖 AI анализирует акции... Это может занять 30–60 секунд"):
            try:
                analysis_text = request_ai_analysis(hits_for_ai)
            except Exception as exc:
                st.error(f"Ошибка AI анализа: {exc}")
                analysis_text = ""

        if analysis_text:
            st.divider()
            st.markdown("### 📊 AI рейтинг и новостной фон")

            top3_text = section_between(
                analysis_text,
                ("## 🏆 TOP-3 SETUPS", "🏆 TOP-3 SETUPS", "TOP-3 SETUPS"),
                ("## ⚪ NEWS WINNER", "⚪ NEWS WINNER", "## 📊 SCORECARD", "📊 SCORECARD"),
                max_chars=4500,
            )
            news_winner_text = section_between(
                analysis_text,
                ("## ⚪ NEWS WINNER", "⚪ NEWS WINNER", "NEWS WINNER"),
                ("## 📊 SCORECARD", "📊 SCORECARD"),
                max_chars=2200,
            )
            scorecard_text = section_between(
                analysis_text,
                ("## 📊 SCORECARD", "📊 SCORECARD", "SCORECARD"),
                tuple(),
                max_chars=3200,
            )

            tab_top, tab_news, tab_score, tab_full = st.tabs(
                ["🏆 TOP-3", "⚪ News winner", "📊 Scorecard", "📄 Полный анализ"]
            )

            with tab_top:
                if top3_text:
                    st.markdown(top3_text)
                else:
                    st.warning("AI не выделил TOP-3 в ожидаемом формате. Смотри полный анализ.")

            with tab_news:
                if news_winner_text:
                    st.info(news_winner_text)
                else:
                    st.warning("AI не выделил NEWS WINNER в ожидаемом формате. Смотри полный анализ.")

            with tab_score:
                if scorecard_text:
                    st.markdown(scorecard_text)
                else:
                    st.warning("AI не вернул SCORECARD в ожидаемом формате. Смотри полный анализ.")

            with tab_full:
                st.markdown(analysis_text)

