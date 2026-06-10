from __future__ import annotations

import html
import logging
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None


# ── APP CONFIG ─────────────────────────────────────────────────────
st.set_page_config(page_title="Скринер накопления", page_icon="📊", layout="wide")


def apply_custom_theme() -> None:
    st.markdown(
        """
        <style>
            :root {
                --desk-bg: #f6f7f9;
                --desk-ink: #111827;
                --desk-muted: #667085;
                --desk-line: #d8dde6;
                --desk-panel: #ffffff;
                --desk-green: #047857;
                --desk-red: #b42318;
                --desk-amber: #b54708;
                --desk-blue: #175cd3;
            }

            .stApp {
                background: var(--desk-bg);
                color: var(--desk-ink);
            }

            section[data-testid="stSidebar"] {
                background: #ffffff;
                border-right: 1px solid var(--desk-line);
            }

            section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
                color: var(--desk-muted);
            }

            .block-container {
                padding-top: 3rem;
                padding-bottom: 2rem;
                max-width: 1480px;
            }

            h1, h2, h3 {
                letter-spacing: 0;
            }

            div[data-testid="stMetric"] {
                background: var(--desk-panel);
                border: 1px solid var(--desk-line);
                border-radius: 8px;
                padding: 0.7rem 0.85rem;
                box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
            }

            div[data-testid="stMetricLabel"] p {
                color: var(--desk-muted);
                font-size: 0.78rem;
            }

            div[data-testid="stMetricValue"] {
                font-size: 1.35rem;
            }

            .desk-header {
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 1rem;
                margin-bottom: 0.85rem;
            }

            .desk-title {
                font-size: 1.65rem;
                font-weight: 750;
                line-height: 1.15;
                margin: 0;
            }

            .desk-subtitle {
                margin-top: 0.25rem;
                color: var(--desk-muted);
                font-size: 0.92rem;
            }

            .desk-chipbar {
                display: flex;
                flex-wrap: wrap;
                gap: 0.45rem;
                margin: 0.45rem 0 1rem;
            }

            .desk-chip {
                display: inline-flex;
                align-items: center;
                gap: 0.35rem;
                border: 1px solid var(--desk-line);
                border-radius: 999px;
                background: #ffffff;
                color: #344054;
                padding: 0.32rem 0.62rem;
                font-size: 0.78rem;
                line-height: 1.1;
            }

            .desk-chip strong {
                color: var(--desk-ink);
                font-weight: 650;
            }

            .desk-chip.green { border-color: #a6f4c5; color: var(--desk-green); background: #ecfdf3; }
            .desk-chip.red { border-color: #fecdca; color: var(--desk-red); background: #fff1f0; }
            .desk-chip.amber { border-color: #fedf89; color: var(--desk-amber); background: #fffaeb; }
            .desk-chip.blue { border-color: #b2ddff; color: var(--desk-blue); background: #eff8ff; }

            .desk-section-title {
                font-size: 0.82rem;
                text-transform: uppercase;
                color: var(--desk-muted);
                letter-spacing: 0.04em;
                font-weight: 700;
                margin: 0.4rem 0 0.2rem;
            }

            .desk-panel {
                background: var(--desk-panel);
                border: 1px solid var(--desk-line);
                border-radius: 8px;
                padding: 0.85rem 1rem;
                margin-bottom: 0.8rem;
            }

            .desk-panel-title {
                font-weight: 700;
                margin-bottom: 0.15rem;
            }

            .leader-card {
                background: #ffffff;
                border: 1px solid var(--desk-line);
                border-radius: 8px;
                padding: 0.95rem 1rem;
                min-height: 185px;
                margin-bottom: 0.8rem;
                box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
            }

            .leader-kicker {
                color: var(--desk-muted);
                font-size: 0.76rem;
                font-weight: 750;
                letter-spacing: 0.04em;
                text-transform: uppercase;
                margin-bottom: 0.35rem;
            }

            .leader-symbol {
                font-size: 1.65rem;
                font-weight: 780;
                line-height: 1.1;
                margin-bottom: 0.3rem;
            }

            .leader-line {
                color: #344054;
                font-size: 0.88rem;
                margin-top: 0.25rem;
            }

            .leader-note {
                color: var(--desk-muted);
                font-size: 0.82rem;
                margin-top: 0.55rem;
            }

            .desk-muted {
                color: var(--desk-muted);
                font-size: 0.88rem;
            }

            div[data-testid="stDataFrame"] {
                border: 1px solid var(--desk-line);
                border-radius: 8px;
                overflow: hidden;
                background: #ffffff;
            }

            div.stButton > button[kind="primary"] {
                background: var(--desk-blue);
                border-color: var(--desk-blue);
                color: #ffffff;
            }

            div.stButton > button[kind="primary"]:hover {
                background: #1849a9;
                border-color: #1849a9;
                color: #ffffff;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def chip(label: str, value: Any, tone: str = "") -> str:
    tone_class = f" {tone}" if tone else ""
    return f'<span class="desk-chip{tone_class}">{html.escape(label)} <strong>{html.escape(str(value))}</strong></span>'


apply_custom_theme()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("accumulation_breakout")

MARKET_TZ = ZoneInfo("America/New_York")
ALPACA_BASE = "https://data.alpaca.markets"
DATA_TIMEOUT_SEC = 15
NASDAQ_TIMEOUT_SEC = 20
BATCH_SIZE = 120
MAX_BARS_PAGES = 25
YAHOO_FALLBACK_CAP = 60

SIG_UP = "BREAKOUT_UP"
SIG_DOWN = "BREAKDOWN"
SIG_SURGE = "VOLUME_SURGE"

SIGNAL_LABELS = {
    SIG_UP: "ПРОБОЙ ВВЕРХ",
    SIG_DOWN: "ПРОБОЙ ВНИЗ",
    SIG_SURGE: "РАННИЙ ОБЪЁМ В КАНАЛЕ",
}
SIGNAL_ICONS = {SIG_UP: "🟢", SIG_DOWN: "🔴", SIG_SURGE: "🔥"}

DISPLAY_COLS = [
    "Тикер",
    "Название",
    "Биржа",
    "Сигнал",
    "Цена",
    "Выход %",
    "Объём ×",
    "Объём",
    "Ср. объём канала",
    "Ширина канала",
    "Канал",
    "Тело свечи %",
    "Долларовый объём",
    "Балл",
    "Источник",
    "Время",
]


LOCAL_SECRETS_CACHE: dict[str, Any] | None = None


def load_local_secrets() -> dict[str, Any]:
    global LOCAL_SECRETS_CACHE
    if LOCAL_SECRETS_CACHE is not None:
        return LOCAL_SECRETS_CACHE

    path = Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
    if not path.exists():
        LOCAL_SECRETS_CACHE = {}
        return LOCAL_SECRETS_CACHE

    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except Exception as exc:
        LOGGER.warning("Could not read local Streamlit secrets: %s", exc)
        data = {}

    LOCAL_SECRETS_CACHE = data
    return LOCAL_SECRETS_CACHE


def secret_or_default(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    if value not in {None, ""}:
        return str(value)

    value = os.environ.get(name)
    if value:
        return str(value)

    value = load_local_secrets().get(name, default)
    return str(value or default)


# Public-safe: keep real values only in Streamlit secrets, never in source code.
TELEGRAM_TOKEN = secret_or_default("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = secret_or_default("TELEGRAM_CHAT_ID")

ALPACA_KEY = secret_or_default("ALPACA_KEY")
ALPACA_SECRET = secret_or_default("ALPACA_SECRET")
ALPACA_HEADERS = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET,
}


@dataclass(frozen=True)
class ScanConfig:
    channel_days: int = 14
    max_channel_width_pct: float = 8.0
    price_basis: str = "HIGH_LOW"  # HIGH_LOW / CLOSE

    require_price_break: bool = True
    allow_volume_alert_inside_channel: bool = False
    breakout_buffer_pct: float = 0.5
    directions: str = "ALL"  # ALL / UP / DOWN

    volume_baseline: str = "MAX"  # MAX / AVG
    min_volume_mult: float = 2.0
    min_channel_avg_volume: int = 100_000
    min_dollar_volume: int = 250_000

    max_gap_pct: float = 8.0
    max_stale_days: int = 5
    min_price: float = 0.5
    max_price: float = 20.0
    feed: str = "iex"


def now_et() -> datetime:
    return datetime.now(MARKET_TZ)


def now_et_str(fmt: str = "%H:%M:%S ET") -> str:
    return now_et().strftime(fmt)


def parse_number(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    text = str(value).replace("$", "").replace(",", "").replace("%", "").strip()
    if not text or text.upper() in {"N/A", "NA", "NONE", "-", "—"}:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def parse_price(value: Any) -> float | None:
    price = parse_number(value)
    return price if price and price > 0 else None


def chunks(items: list[Any], size: int) -> Iterator[list[Any]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def normalize_symbol(symbol: str, name: str = "") -> str | None:
    sym = (symbol or "").strip().upper().replace("/", "-").replace(".", "-")
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
        data["Date"] = pd.to_datetime(data["Date"], errors="coerce", utc=True)
        data.set_index("Date", inplace=True)

    required = ["Open", "High", "Low", "Close", "Volume"]
    if any(col not in data.columns for col in required):
        return None

    data = data[required].copy()
    for col in required:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    data = data.dropna(subset=required).sort_index()
    data = data[
        (data["Open"] > 0)
        & (data["High"] > 0)
        & (data["Low"] > 0)
        & (data["Close"] > 0)
        & (data["Volume"] >= 0)
    ]
    if data.empty:
        return None
    data.attrs["source"] = source
    return data


def get_market_status() -> tuple[str, str]:
    current = now_et()
    minute = current.hour * 60 + current.minute
    if 4 * 60 <= minute < 9 * 60 + 30:
        return "info", "Pre-Market активен (4:00-9:30 ET)"
    if 9 * 60 + 30 <= minute <= 16 * 60:
        return "success", "Основная сессия открыта (9:30-16:00 ET)"
    if 16 * 60 < minute <= 20 * 60:
        return "info", "Post-Market активен (16:00-20:00 ET)"
    return "warning", "Рынок закрыт"


def remember_error(message: str) -> None:
    errors = st.session_state.setdefault("scan_errors", [])
    errors.append(f"{now_et_str()} · {message}")
    del errors[:-15]


# ── TICKER UNIVERSE ────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_nasdaq_tickers(exchange: str, max_price: float) -> list[dict[str, Any]]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://www.nasdaq.com/",
    }
    exchanges = ["nasdaq", "nyse", "amex"] if exchange == "ALL" else [exchange.lower()]
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
            LOGGER.warning("Could not load Nasdaq tickers for %s: %s", ex, exc)
            continue

        for row in rows:
            name = row.get("name", "") or ""
            ticker = normalize_symbol(row.get("symbol", ""), name)
            if not ticker or ticker in seen:
                continue
            price = parse_price(row.get("lastsale"))
            if price is None or price > max_price:
                continue
            seen.add(ticker)
            tickers.append(
                {
                    "ticker": ticker,
                    "exchange": ex.upper(),
                    "name": name,
                    "price_api": price,
                }
            )

    if tickers:
        return tickers

    fallback = ["SBET", "PLTR", "SOUN", "QBTS", "OPEN", "SOFI", "HIMS", "PLUG", "RIVN", "LCID"]
    return [{"ticker": ticker, "exchange": "US", "name": "", "price_api": 0.0} for ticker in fallback]


# ── DATA SOURCES ──────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def fetch_alpaca_batch(symbols: tuple[str, ...], days: int, feed: str) -> dict[str, pd.DataFrame]:
    if not (ALPACA_KEY and ALPACA_SECRET) or not symbols:
        return {}

    end = now_et().date()
    start = end - timedelta(days=max(60, days * 4))
    raw: dict[str, list[dict[str, Any]]] = {}
    page_token: str | None = None

    for _ in range(MAX_BARS_PAGES):
        params: dict[str, Any] = {
            "symbols": ",".join(symbols),
            "timeframe": "1Day",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": 10000,
            "feed": feed,
            "adjustment": "split",
            "sort": "asc",
        }
        if page_token:
            params["page_token"] = page_token

        try:
            resp = requests.get(
                f"{ALPACA_BASE}/v2/stocks/bars",
                headers=ALPACA_HEADERS,
                params=params,
                timeout=DATA_TIMEOUT_SEC,
            )
            if resp.status_code in {401, 403}:
                LOGGER.warning("Alpaca auth failed: %s", resp.status_code)
                return {}
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            LOGGER.info("Alpaca batch failed: %s", exc)
            break

        for symbol, bars in (payload.get("bars") or {}).items():
            raw.setdefault(str(symbol).upper(), []).extend(bars or [])

        page_token = payload.get("next_page_token")
        if not page_token:
            break

    out: dict[str, pd.DataFrame] = {}
    for symbol, bars in raw.items():
        df = normalize_ohlcv(pd.DataFrame(bars), f"Alpaca {feed.upper()}")
        if df is not None and len(df) >= days + 2:
            out[symbol] = df
    return out


@st.cache_data(ttl=60, show_spinner=False)
def fetch_yahoo_daily(ticker: str, days: int) -> pd.DataFrame | None:
    if yf is None:
        return None

    period = "90d" if days <= 20 else "6mo"
    try:
        df = yf.download(
            ticker,
            period=period,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
            timeout=DATA_TIMEOUT_SEC,
        )
    except Exception as exc:
        LOGGER.info("Yahoo failed for %s: %s", ticker, exc)
        return None
    return normalize_ohlcv(df, "Yahoo Finance")


def load_bars(
    ticker_infos: list[dict[str, Any]],
    cfg: ScanConfig,
    source_mode: str,
    progress_box: Any,
    status_box: Any,
) -> dict[str, pd.DataFrame]:
    symbols = [str(item["ticker"]).upper() for item in ticker_infos]
    bars: dict[str, pd.DataFrame] = {}

    use_alpaca = source_mode in {"Alpaca first", "Alpaca only"}
    use_yahoo = source_mode in {"Alpaca first", "Yahoo only"}

    if use_alpaca:
        batches = list(chunks(symbols, BATCH_SIZE))
        for idx, batch in enumerate(batches, start=1):
            status_box.caption(f"Загружаю Alpaca · пачка {idx}/{len(batches)} · готово: {len(bars)}")
            bars.update(fetch_alpaca_batch(tuple(batch), cfg.channel_days, cfg.feed))
            if not use_yahoo:
                progress_box.progress(idx / max(len(batches), 1))
            else:
                progress_box.progress(0.65 * idx / max(len(batches), 1))

    if use_yahoo:
        missing = symbols if source_mode == "Yahoo only" else [symbol for symbol in symbols if symbol not in bars]
        if source_mode != "Yahoo only":
            missing = missing[:YAHOO_FALLBACK_CAP]

        for idx, symbol in enumerate(missing, start=1):
            status_box.caption(f"Yahoo резерв · {symbol} ({idx}/{len(missing)})")
            df = fetch_yahoo_daily(symbol, cfg.channel_days)
            if df is not None:
                bars[symbol] = df
            base = 0.65 if use_alpaca else 0.0
            progress_box.progress(min(1.0, base + (1.0 - base) * idx / max(len(missing), 1)))

    progress_box.progress(0.7)
    return bars


# ── SIGNAL LOGIC ──────────────────────────────────────────────────
@dataclass(frozen=True)
class Channel:
    low: float
    high: float
    width_pct: float
    vol_max: float
    vol_avg: float
    avg_dollar_volume: float
    max_gap_pct: float


def build_channel(df: pd.DataFrame, cfg: ScanConfig) -> Channel | None:
    if len(df) < cfg.channel_days + 2:
        return None

    window = df.iloc[-(cfg.channel_days + 1) : -1].copy()
    if len(window) < cfg.channel_days:
        return None

    if cfg.price_basis == "HIGH_LOW":
        channel_low = float(window["Low"].min())
        channel_high = float(window["High"].max())
    else:
        channel_low = float(window["Close"].min())
        channel_high = float(window["Close"].max())

    if channel_low <= 0 or channel_high <= channel_low:
        return None

    volumes = window["Volume"][window["Volume"] > 0]
    if volumes.empty:
        return None

    prev_close = window["Close"].shift(1)
    gaps = ((window["Open"] - prev_close).abs() / prev_close * 100).dropna()
    max_gap = float(gaps.max()) if not gaps.empty else 0.0

    return Channel(
        low=channel_low,
        high=channel_high,
        width_pct=(channel_high - channel_low) / channel_low * 100,
        vol_max=float(volumes.max()),
        vol_avg=float(volumes.mean()),
        avg_dollar_volume=float((window["Close"] * window["Volume"]).mean()),
        max_gap_pct=max_gap,
    )


def score_signal(
    signal_code: str,
    channel_width: float,
    volume_mult: float,
    breakout_pct: float,
    max_gap_pct: float,
    cfg: ScanConfig,
) -> int:
    volume_score = min(45.0, volume_mult / max(cfg.min_volume_mult, 0.1) * 22.5)
    channel_score = max(
        0.0,
        min(25.0, (cfg.max_channel_width_pct - channel_width) / max(cfg.max_channel_width_pct, 0.1) * 25.0),
    )
    breakout_score = min(20.0, abs(breakout_pct) * 2.5)
    if signal_code == SIG_SURGE:
        breakout_score = min(breakout_score, 6.0)
    gap_score = max(0.0, min(10.0, (1 - max_gap_pct / max(cfg.max_gap_pct, 0.1)) * 10.0))
    return int(round(volume_score + channel_score + breakout_score + gap_score))


def detect_signal(
    ticker_info: dict[str, Any],
    df: pd.DataFrame,
    cfg: ScanConfig,
    today: Any | None = None,
) -> dict[str, Any] | None:
    if df is None or len(df) < cfg.channel_days + 2:
        return None

    df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
    if len(df) < cfg.channel_days + 2:
        return None

    if today is None:
        today = now_et().date()
    try:
        age_days = (today - df.index[-1].date()).days
    except Exception:
        age_days = 0
    if age_days > cfg.max_stale_days:
        return None

    latest = df.iloc[-1]
    price = float(latest["Close"])
    latest_volume = float(latest["Volume"])
    latest_open = float(latest["Open"])
    if price <= 0 or latest_volume <= 0 or latest_open <= 0:
        return None
    if price < cfg.min_price or price > cfg.max_price:
        return None

    channel = build_channel(df, cfg)
    if channel is None:
        return None
    if channel.width_pct > cfg.max_channel_width_pct:
        return None
    if channel.vol_avg < cfg.min_channel_avg_volume:
        return None
    if price * latest_volume < cfg.min_dollar_volume:
        return None
    if channel.max_gap_pct > cfg.max_gap_pct:
        return None

    upper = channel.high * (1 + cfg.breakout_buffer_pct / 100)
    lower = channel.low * (1 - cfg.breakout_buffer_pct / 100)

    breakout_up_pct = (price - channel.high) / channel.high * 100
    breakdown_down_pct = (channel.low - price) / channel.low * 100
    body_pct = abs(price - latest_open) / latest_open * 100

    volume_ref = channel.vol_max if cfg.volume_baseline == "MAX" else channel.vol_avg
    if volume_ref <= 0:
        return None
    volume_mult = latest_volume / volume_ref
    volume_ok = volume_mult >= cfg.min_volume_mult
    if not volume_ok:
        return None

    signal_code = None
    move_pct = 0.0
    if price > upper:
        signal_code = SIG_UP
        move_pct = breakout_up_pct
    elif price < lower:
        signal_code = SIG_DOWN
        move_pct = -breakdown_down_pct
    elif cfg.allow_volume_alert_inside_channel and not cfg.require_price_break:
        signal_code = SIG_SURGE
        move_pct = 0.0

    if signal_code is None:
        return None
    if cfg.directions == "UP" and signal_code != SIG_UP:
        return None
    if cfg.directions == "DOWN" and signal_code != SIG_DOWN:
        return None

    score = score_signal(signal_code, channel.width_pct, volume_mult, move_pct, channel.max_gap_pct, cfg)
    signal = SIGNAL_LABELS[signal_code]
    return {
        "_sig": signal_code,
        "_rvol": volume_mult,
        "_score": score,
        "_width": channel.width_pct,
        "Тикер": ticker_info["ticker"],
        "Название": (ticker_info.get("name") or "")[:34],
        "Биржа": ticker_info.get("exchange", ""),
        "Сигнал": signal,
        "Цена": round(price, 4),
        "Выход %": f"{move_pct:+.1f}%" if move_pct else "—",
        "Объём ×": round(volume_mult, 2),
        "Объём": int(latest_volume),
        "Ср. объём канала": int(channel.vol_avg),
        "Ширина канала": f"{channel.width_pct:.1f}%",
        "Канал": f"${channel.low:.4f}-${channel.high:.4f}",
        "Тело свечи %": round(body_pct, 1),
        "Долларовый объём": int(price * latest_volume),
        "Балл": score,
        "Источник": df.attrs.get("source", ""),
        "Время": now_et_str(),
    }


def scan_market(
    ticker_infos: list[dict[str, Any]],
    cfg: ScanConfig,
    source_mode: str,
    progress_box: Any,
    status_box: Any,
    table_box: Any,
    send_alerts: bool,
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    total = len(ticker_infos)
    st.session_state.stats = {"checked": 0, "signals": 0}
    st.session_state.scan_errors = []

    bars = load_bars(ticker_infos, cfg, source_mode, progress_box, status_box)
    today = now_et().date()

    for idx, ticker_info in enumerate(ticker_infos, start=1):
        ticker = ticker_info["ticker"]
        progress_box.progress(min(1.0, 0.7 + 0.3 * idx / max(total, 1)))
        if idx % 50 == 1 or idx == total:
            status_box.caption(f"Анализирую {idx}/{total} · найдено: {len(hits)}")

        try:
            history = bars.get(str(ticker).upper())
            if history is None:
                st.session_state.stats["checked"] = idx
                continue
            row = detect_signal(ticker_info, history, cfg, today)
        except Exception as exc:
            LOGGER.exception("Scan failed for %s", ticker)
            remember_error(f"{ticker}: {exc}")
            row = None

        if row:
            hits.append(row)
            st.session_state.stats["signals"] = len(hits)
            table_box.dataframe(display_frame(hits), use_container_width=True, hide_index=True)
            if send_alerts and should_notify(row):
                send_telegram(telegram_signal_message(row))

        st.session_state.stats["checked"] = idx

    return sorted(
        hits,
        key=lambda row: (int(row["Балл"]), float(row["Объём ×"]), -float(str(row["Ширина канала"]).rstrip("%"))),
        reverse=True,
    )


# ── TELEGRAM ──────────────────────────────────────────────────────
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


def should_notify(row: dict[str, Any]) -> bool:
    notified = st.session_state.setdefault("notified_signals", set())
    key = f"{now_et().date().isoformat()}:{row['Тикер']}:{row.get('_sig', row['Сигнал'])}"
    if key in notified:
        return False
    notified.add(key)
    return True


def telegram_signal_message(row: dict[str, Any]) -> str:
    ticker = html.escape(str(row["Тикер"]))
    signal_text = str(row["Сигнал"])
    signal = html.escape(signal_text)
    icon = SIGNAL_ICONS.get(
        str(row.get("_sig", "")),
        "🟢" if ("ВВЕРХ" in signal_text or "UP" in signal_text) else ("🔴" if ("ВНИЗ" in signal_text or "DOWN" in signal_text) else "🔥"),
    )
    return (
        f"{icon} <b>ACCUMULATION BREAKOUT</b>\n"
        f"<b>{ticker}</b> · {signal} · ${row['Цена']}\n"
        f"Выход: {row['Выход %']} | Объём ×{row['Объём ×']}\n"
        f"Канал: {row['Канал']} | Ширина: {row['Ширина канала']}\n"
        f"Балл: {row['Балл']}/100 | Источник: {html.escape(str(row['Источник']))}\n"
        f"⏰ {now_et_str('%H:%M ET')}"
    )


def result_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("Тикер", "")), str(row.get("Сигнал", ""))


def merge_results(new_rows: list[dict[str, Any]], old_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for row in old_rows:
        merged[result_key(row)] = row
    for row in new_rows:
        merged[result_key(row)] = row
    return sorted(merged.values(), key=lambda row: int(row.get("Балл", 0)), reverse=True)


def display_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=DISPLAY_COLS)
    frame = pd.DataFrame(rows)
    columns = [col for col in DISPLAY_COLS if col in frame.columns]
    return frame[columns]


# ── MARKET ROUTE ────────────────────────────────────────────────────
def total_pages_for(total_items: int, page_size: int) -> int:
    return max(1, (max(0, int(total_items)) + max(1, int(page_size)) - 1) // max(1, int(page_size)))


def effective_route_pages(total_pages: int, requested_pages: int) -> int:
    requested = int(requested_pages or 0)
    if requested <= 0:
        return max(1, int(total_pages))
    return max(1, min(int(requested), int(total_pages)))


def clamp_page(page: int, route_pages: int) -> int:
    return max(1, min(int(page), max(1, int(route_pages))))


def next_route_page(current_page: int, route_pages: int) -> tuple[int, bool]:
    current = clamp_page(current_page, route_pages)
    if current >= route_pages:
        return 1, True
    return current + 1, False


# ── LEADER ANALYSIS ─────────────────────────────────────────────────
POSITIVE_NEWS_TERMS: tuple[tuple[str, int], ...] = (
    ("upgrade", 10),
    ("raised price target", 9),
    ("raises guidance", 9),
    ("beats estimates", 9),
    ("beat expectations", 9),
    ("record revenue", 8),
    ("profit", 7),
    ("profitable", 7),
    ("approval", 7),
    ("fda approval", 9),
    ("contract", 7),
    ("partnership", 6),
    ("launch", 5),
    ("acquisition", 5),
    ("buyout", 8),
    ("secures", 6),
    ("expands", 5),
    ("surges", 5),
    ("rallies", 5),
)

NEGATIVE_NEWS_TERMS: tuple[tuple[str, int], ...] = (
    ("downgrade", 10),
    ("cuts guidance", 10),
    ("misses estimates", 9),
    ("missed expectations", 9),
    ("offering", 9),
    ("dilution", 10),
    ("lawsuit", 8),
    ("investigation", 8),
    ("sec probe", 10),
    ("bankruptcy", 12),
    ("delisting", 12),
    ("reverse split", 9),
    ("fraud", 12),
    ("loss widens", 8),
    ("plunges", 7),
    ("falls", 5),
    ("cuts", 5),
)


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).replace("$", "").replace(",", "").replace("%", "").strip()
    if not text or text == "—":
        return default
    try:
        return float(text)
    except ValueError:
        return default


def compact_number(value: Any) -> str:
    number = safe_float(value)
    if number >= 1_000_000_000:
        return f"{number / 1_000_000_000:.1f}B"
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    if number >= 1_000:
        return f"{number / 1_000:.1f}K"
    return f"{number:.0f}"


def technical_rank(row: dict[str, Any]) -> float:
    score = safe_float(row.get("Балл"))
    volume_mult = safe_float(row.get("Объём ×"))
    channel_width = safe_float(row.get("Ширина канала"))
    dollar_volume = safe_float(row.get("Долларовый объём"))
    signal = str(row.get("Сигнал", ""))

    direction_bonus = 8.0 if "ВВЕРХ" in signal or "UP" in signal else 0.0
    early_bonus = 4.0 if "ОБЪЁМ" in signal or "VOLUME" in signal else 0.0
    channel_bonus = max(0.0, 12.0 - channel_width)
    liquidity_bonus = min(10.0, dollar_volume / 1_000_000)
    volume_bonus = min(14.0, volume_mult * 2.0)
    return score + direction_bonus + early_bonus + channel_bonus + liquidity_bonus + volume_bonus


def clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_news_item(raw: dict[str, Any], source: str) -> dict[str, str]:
    return {
        "title": clean_text(raw.get("headline") or raw.get("title")),
        "summary": clean_text(raw.get("summary") or raw.get("description")),
        "source": clean_text(raw.get("source") or source),
        "url": str(raw.get("url") or raw.get("link") or ""),
        "time": clean_text(raw.get("created_at") or raw.get("pubDate") or raw.get("published") or ""),
    }


@st.cache_data(ttl=900, show_spinner=False)
def fetch_alpaca_news_batch(symbols: tuple[str, ...], limit: int, days: int) -> dict[str, list[dict[str, str]]]:
    if not ALPACA_KEY or not ALPACA_SECRET or not symbols:
        return {}

    end = now_et()
    start = end - timedelta(days=days)
    try:
        resp = requests.get(
            f"{ALPACA_BASE}/v1beta1/news",
            headers=ALPACA_HEADERS,
            params={
                "symbols": ",".join(symbols),
                "limit": limit,
                "sort": "desc",
                "include_content": "false",
                "start": start.isoformat(),
                "end": end.isoformat(),
            },
            timeout=DATA_TIMEOUT_SEC,
        )
        if resp.status_code in {401, 403, 404}:
            return {}
        resp.raise_for_status()
        rows = resp.json().get("news", []) or []
    except Exception as exc:
        LOGGER.info("Alpaca news batch failed: %s", exc)
        return {}

    out: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        item = normalize_news_item(row, "Alpaca News")
        if not item["title"]:
            continue
        for symbol in row.get("symbols", []) or []:
            out.setdefault(str(symbol).upper(), []).append(item)
    return out


@st.cache_data(ttl=900, show_spinner=False)
def fetch_alpaca_news(ticker: str, limit: int, days: int) -> list[dict[str, str]]:
    if not ALPACA_KEY or not ALPACA_SECRET:
        return []

    end = now_et()
    start = end - timedelta(days=days)
    try:
        resp = requests.get(
            f"{ALPACA_BASE}/v1beta1/news",
            headers=ALPACA_HEADERS,
            params={
                "symbols": ticker,
                "limit": limit,
                "sort": "desc",
                "include_content": "false",
                "start": start.isoformat(),
                "end": end.isoformat(),
            },
            timeout=DATA_TIMEOUT_SEC,
        )
        if resp.status_code in {401, 403, 404}:
            return []
        resp.raise_for_status()
        rows = resp.json().get("news", []) or []
    except Exception as exc:
        LOGGER.info("Alpaca news failed for %s: %s", ticker, exc)
        return []

    return [normalize_news_item(row, "Alpaca News") for row in rows if row.get("headline") or row.get("title")]


@st.cache_data(ttl=900, show_spinner=False)
def fetch_yahoo_news(ticker: str, limit: int) -> list[dict[str, str]]:
    try:
        resp = requests.get(
            "https://feeds.finance.yahoo.com/rss/2.0/headline",
            params={"s": ticker, "region": "US", "lang": "en-US"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=DATA_TIMEOUT_SEC,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as exc:
        LOGGER.info("Yahoo news failed for %s: %s", ticker, exc)
        return []

    items: list[dict[str, str]] = []
    for item in root.findall(".//item")[:limit]:
        items.append(
            normalize_news_item(
                {
                    "title": item.findtext("title"),
                    "description": item.findtext("description"),
                    "link": item.findtext("link"),
                    "pubDate": item.findtext("pubDate"),
                },
                "Yahoo RSS",
            )
        )
    return [item for item in items if item["title"]]


def fetch_news_for_ticker(ticker: str, limit: int = 6, days: int = 7) -> tuple[list[dict[str, str]], str]:
    alpaca_items = fetch_alpaca_news(ticker, limit, days)
    if alpaca_items:
        return alpaca_items, "Alpaca News"

    yahoo_items = fetch_yahoo_news(ticker, limit)
    if yahoo_items:
        return yahoo_items, "Yahoo RSS"

    return [], "нет свежих новостей"


def score_news_items(items: list[dict[str, str]]) -> dict[str, Any]:
    if not items:
        return {
            "score": 0,
            "tone": "новостей нет",
            "reasons": ["свежие новости не найдены"],
            "headline": "Свежие новости не найдены",
        }

    text = " ".join(f"{item.get('title', '')} {item.get('summary', '')}" for item in items).lower()
    positive_hits = [(term, weight) for term, weight in POSITIVE_NEWS_TERMS if term in text]
    negative_hits = [(term, weight) for term, weight in NEGATIVE_NEWS_TERMS if term in text]

    score = 50 + min(12, len(items) * 3)
    score += sum(weight for _, weight in positive_hits)
    score -= sum(weight for _, weight in negative_hits)
    score = max(0, min(100, int(score)))

    if score >= 68:
        tone = "позитивный"
    elif score >= 45:
        tone = "нейтральный"
    else:
        tone = "рискованный"

    reasons: list[str] = []
    if positive_hits:
        reasons.append("позитив: " + ", ".join(term for term, _ in positive_hits[:3]))
    if negative_hits:
        reasons.append("риски: " + ", ".join(term for term, _ in negative_hits[:3]))
    if not reasons:
        reasons.append("явных сильных слов в заголовках нет")

    return {
        "score": score,
        "tone": tone,
        "reasons": reasons,
        "headline": items[0].get("title", "Новость без заголовка"),
    }


def build_leader_analysis(rows: list[dict[str, Any]], news_candidates: int) -> dict[str, Any] | None:
    clean_rows = [row for row in rows if isinstance(row, dict) and row.get("Тикер")]
    if not clean_rows:
        return None

    ranked_rows = sorted(clean_rows, key=technical_rank, reverse=True)
    technical = ranked_rows[0]
    top_rows = ranked_rows[: max(2, int(news_candidates))]
    symbols = tuple({str(row.get("Тикер", "")).upper() for row in top_rows if row.get("Тикер")})
    alpaca_news = fetch_alpaca_news_batch(symbols, 50, 7)

    news_scores: list[dict[str, Any]] = []
    for row in top_rows:
        ticker = str(row.get("Тикер", ""))
        items = alpaca_news.get(ticker.upper(), [])
        source = "Alpaca News"
        if not items:
            items = fetch_yahoo_news(ticker, 6)
            source = "Yahoo RSS" if items else "нет свежих новостей"
        news_score = score_news_items(items)
        news_scores.append(
            {
                "row": row,
                "source": source,
                "items": items,
                "news_score": news_score,
                "technical_rank": technical_rank(row),
            }
        )

    news_with_items = [item for item in news_scores if item["items"]]
    news_leader = max(
        news_with_items,
        key=lambda item: (item["news_score"]["score"], item["technical_rank"]),
        default=None,
    )

    return {
        "technical": technical,
        "technical_rank": technical_rank(technical),
        "news": news_leader,
        "checked_news": len(news_scores),
        "created_at": now_et_str(),
    }


def telegram_leader_message(analysis: dict[str, Any]) -> str:
    tech = analysis["technical"]
    lines = [
        "🏁 <b>Разбор лидеров скринера</b>",
        (
            "💪 Техника: "
            f"<b>{html.escape(str(tech['Тикер']))}</b> · {html.escape(str(tech['Сигнал']))} · "
            f"балл {tech['Балл']}/100 · объём ×{tech['Объём ×']} · канал {html.escape(str(tech['Ширина канала']))}"
        ),
    ]

    news = analysis.get("news")
    if news:
        row = news["row"]
        score = news["news_score"]
        headline = html.escape(str(score["headline"])[:180])
        lines.append(
            "📰 Новости: "
            f"<b>{html.escape(str(row['Тикер']))}</b> · фон {score['score']}/100 · "
            f"{html.escape(str(score['tone']))} · {headline}"
        )
    else:
        lines.append("📰 Новости: по найденным сигналам свежий новостной лидер не найден.")

    lines.append(f"⏰ {now_et_str('%H:%M ET')}")
    return "\n".join(lines)


def render_leader_analysis(analysis: dict[str, Any]) -> None:
    tech = analysis["technical"]
    news = analysis.get("news")

    st.markdown('<div class="desk-section-title">Разбор лидеров</div>', unsafe_allow_html=True)
    tech_col, news_col = st.columns(2)

    with tech_col:
        st.markdown(
            f"""
            <div class="leader-card">
                <div class="leader-kicker">Самый сильный технический сигнал</div>
                <div class="leader-symbol">{html.escape(str(tech["Тикер"]))}</div>
                <div class="leader-line"><b>{html.escape(str(tech["Сигнал"]))}</b> · балл {html.escape(str(tech["Балл"]))}/100</div>
                <div class="leader-line">Объём: ×{html.escape(str(tech["Объём ×"]))} · канал: {html.escape(str(tech["Ширина канала"]))}</div>
                <div class="leader-line">Цена: ${html.escape(str(tech["Цена"]))} · долларовый объём: ${compact_number(tech.get("Долларовый объём"))}</div>
                <div class="leader-note">Выбрано по сумме: балл сигнала, всплеск объёма, узость канала, ликвидность и направление.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with news_col:
        if news:
            row = news["row"]
            score = news["news_score"]
            st.markdown(
                f"""
                <div class="leader-card">
                    <div class="leader-kicker">Самый сильный новостной фон</div>
                    <div class="leader-symbol">{html.escape(str(row["Тикер"]))}</div>
                    <div class="leader-line"><b>Фон: {score["score"]}/100</b> · {html.escape(str(score["tone"]))} · {html.escape(str(news["source"]))}</div>
                    <div class="leader-line">Техника: {html.escape(str(row["Сигнал"]))} · балл {html.escape(str(row["Балл"]))}/100</div>
                    <div class="leader-note">{html.escape("; ".join(score["reasons"]))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.expander(f"Новости по {row['Тикер']}"):
                for item in news["items"][:4]:
                    title = item["title"]
                    url = item.get("url", "")
                    source = item.get("source", news["source"])
                    if url:
                        st.markdown(f"- [{title}]({url}) · {source}")
                    else:
                        st.markdown(f"- {title} · {source}")
        else:
            st.markdown(
                """
                <div class="leader-card">
                    <div class="leader-kicker">Самый сильный новостной фон</div>
                    <div class="leader-symbol">нет данных</div>
                    <div class="leader-line">По найденным сигналам свежие новости не найдены.</div>
                    <div class="leader-note">Для Alpaca News нужны Alpaca secrets; если их нет, код пробует Yahoo RSS.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ── SESSION STATE ─────────────────────────────────────────────────
if "results" not in st.session_state:
    st.session_state.results = []
if "stats" not in st.session_state:
    st.session_state.stats = {"checked": 0, "signals": 0}
if "scan_errors" not in st.session_state:
    st.session_state.scan_errors = []
if "notified_signals" not in st.session_state:
    st.session_state.notified_signals = set()
if "auto_last_run" not in st.session_state:
    st.session_state.auto_last_run = None
elif isinstance(st.session_state.auto_last_run, datetime) and st.session_state.auto_last_run.tzinfo is None:
    st.session_state.auto_last_run = st.session_state.auto_last_run.replace(tzinfo=MARKET_TZ)
if "auto_count" not in st.session_state:
    st.session_state.auto_count = 0
if "leader_analysis" not in st.session_state:
    st.session_state.leader_analysis = None
if "scan_page" not in st.session_state:
    st.session_state.scan_page = 1
if "market_cycles_done" not in st.session_state:
    st.session_state.market_cycles_done = 0
if "last_total_pages" not in st.session_state:
    st.session_state.last_total_pages = None
if "last_route_pages" not in st.session_state:
    st.session_state.last_route_pages = None
if "last_scan_page" not in st.session_state:
    st.session_state.last_scan_page = None
if st.session_state.pop("sync_page_widget", False) or "page_selector" not in st.session_state:
    st.session_state.page_selector = int(st.session_state.scan_page)


# ── SIDEBAR ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Панель скринера")
    st.markdown('<div class="desk-muted">Накопление · канал · выход объёмом</div>', unsafe_allow_html=True)

    st.markdown('<div class="desk-section-title">Данные</div>', unsafe_allow_html=True)
    source_labels = {
        "Alpaca first": "Alpaca сначала, Yahoo резерв",
        "Alpaca only": "Только Alpaca",
        "Yahoo only": "Только Yahoo",
    }
    source_mode = st.selectbox(
        "Источник свечей",
        ["Alpaca first", "Alpaca only", "Yahoo only"],
        index=0,
        format_func=lambda value: source_labels[value],
        help="Alpaca теперь грузится пачками. Yahoo используется как резерв для пропусков.",
    )
    feed_label = st.selectbox(
        "Фид Alpaca",
        ["iex", "sip"],
        index=0,
        format_func=lambda value: f"{value.upper()} {'(бесплатный)' if value == 'iex' else '(платный полный)'}",
    )
    if source_mode != "Alpaca only" and yf is None:
        st.warning("yfinance не установлен: резервный Yahoo недоступен.")
    if feed_label == "iex":
        st.caption("IEX даёт частичный объём рынка; RVOL считается внутри одного фида, поэтому сравнение остаётся полезным.")

    st.markdown('<div class="desk-section-title">Рынок</div>', unsafe_allow_html=True)
    exchange = st.selectbox("Биржа", ["ALL", "NASDAQ", "NYSE", "AMEX"], index=0)
    max_scan_price = st.number_input(
        "Макс. цена для списка рынка",
        min_value=0.1,
        max_value=500.0,
        value=20.0,
        step=1.0,
        help="Фильтр цены применяется ещё на этапе списка рынка.",
    )
    max_tickers = st.slider("Акций за прогон", 50, 10000, 1000, 50)
    page_num = int(st.number_input("Страница маршрута", min_value=1, max_value=500, step=1, key="page_selector"))
    st.session_state.scan_page = page_num
    advance_page_after_scan = st.toggle(
        "После скана переходить дальше",
        value=True,
        help="После каждого ручного или автоматического скана следующая проверка начнётся со следующего блока акций.",
    )
    route_page_limit = st.number_input(
        "Страниц в круге",
        min_value=0,
        max_value=500,
        value=0,
        step=1,
        help="0 = весь доступный рынок. Если указать больше, чем реально есть страниц, код сам ограничит по факту.",
    )
    stop_after_cycles = st.number_input(
        "Остановиться после кругов",
        min_value=0,
        max_value=50,
        value=0,
        step=1,
        help="0 = не останавливать авто-скан. 1 = пройти весь маршрут один раз и ждать ручного сброса.",
    )
    if st.button("Сбросить маршрут на страницу 1", use_container_width=True):
        st.session_state.scan_page = 1
        st.session_state.market_cycles_done = 0
        st.session_state.sync_page_widget = True
        st.rerun()
    if st.session_state.last_route_pages:
        st.caption(
            f"Последний маршрут: стр. {st.session_state.last_scan_page}/{st.session_state.last_route_pages} · "
            f"кругов пройдено: {st.session_state.market_cycles_done}"
        )
    st.caption("NASDAQ/NYSE/AMEX · обычные акции до 5 букв · без ETF, фондов, юнитов, варрантов, прав, привилегированных акций и долговых нот")

    st.markdown('<div class="desk-section-title">Канал накопления</div>', unsafe_allow_html=True)
    channel_days = st.slider("Дней в канале", 10, 25, 14)
    max_channel_width_pct = st.slider("Максимальная ширина канала (%)", 2.0, 25.0, 8.0, 0.5)
    price_basis_label = st.radio(
        "Расчёт канала",
        ["High/Low — максимум и минимум свечей", "Close — только закрытия"],
        index=0,
        horizontal=True,
        help="High/Low строже: берёт весь хвост свечей. Close мягче: смотрит только цены закрытия.",
    )
    price_basis = "HIGH_LOW" if price_basis_label.startswith("High/Low") else "CLOSE"
    max_gap_pct = st.slider("Максимальный гэп внутри канала (%)", 1.0, 30.0, 8.0, 0.5)
    max_stale_days = st.slider(
        "Свежесть последней свечи, дней",
        1,
        10,
        5,
        help="Отбрасывает тикеры, у которых последний дневной бар слишком старый.",
    )

    st.markdown('<div class="desk-section-title">Выход и объём</div>', unsafe_allow_html=True)
    breakout_buffer_pct = st.slider("Буфер выхода за канал (%)", 0.0, 10.0, 0.5, 0.1)
    direction_label = st.radio(
        "Направление",
        ["Все", "Вверх", "Вниз"],
        index=0,
        horizontal=True,
        help="Все: искать выход вверх и вниз. Вверх: только пробой верхней границы. Вниз: только пробой нижней границы.",
    )
    directions = {"Все": "ALL", "Вверх": "UP", "Вниз": "DOWN"}[direction_label]
    signal_style = st.radio(
        "Тип сигнала",
        ["Только выход из канала", "Выход или ранний объём в канале"],
        index=1,
    )
    require_price_break = signal_style == "Только выход из канала"
    allow_volume_alert_inside_channel = signal_style == "Выход или ранний объём в канале"

    st.markdown('<div class="desk-section-title">Объём</div>', unsafe_allow_html=True)
    volume_label = st.radio(
        "Сравнивать объём с",
        ["MAX — максимум канала", "AVG — средний объём канала"],
        index=1,
        horizontal=True,
        help="MAX строже: сегодняшний объём должен быть выше максимального объёма внутри канала. AVG мягче: сравнение со средним объёмом канала.",
    )
    volume_baseline = "MAX" if volume_label.startswith("MAX") else "AVG"
    min_volume_mult = st.slider("Минимальный всплеск объёма ×", 1.0, 10.0, 2.0, 0.25)
    min_channel_avg_volume = st.number_input("Минимальный средний объём канала", 0, 10_000_000, 100_000, 25_000)
    min_dollar_volume = st.number_input("Минимальный долларовый объём сегодня", 0, 100_000_000, 250_000, 50_000)

    st.markdown('<div class="desk-section-title">Цена</div>', unsafe_allow_html=True)
    price_col_1, price_col_2 = st.columns(2)
    with price_col_1:
        min_price = st.number_input("Мин. цена", 0.01, 500.0, 0.5, 0.1)
    with price_col_2:
        max_price = st.number_input("Макс. цена", 0.01, 500.0, 20.0, 1.0)

    st.markdown('<div class="desk-section-title">Разбор лидеров</div>', unsafe_allow_html=True)
    analyze_leaders = st.toggle("Показывать лидеров после скана", value=True)
    news_candidate_count = st.slider(
        "Сколько сильных сигналов проверять по новостям",
        2,
        12,
        6,
        1,
        disabled=not analyze_leaders,
    )
    st.caption("Новости: сначала Alpaca News, если доступны ключи; затем Yahoo RSS как резерв.")

    st.markdown('<div class="desk-section-title">Автоматизация</div>', unsafe_allow_html=True)
    send_alerts = st.toggle("Telegram-уведомления", value=True)
    send_leader_summary = analyze_leaders and send_alerts and st.toggle(
        "Telegram-итог лидеров",
        value=True,
        disabled=not send_alerts,
    )
    telegram_configured = bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)
    if st.button("Отправить тест Telegram", use_container_width=True, disabled=not telegram_configured):
        if send_telegram(f"✅ Тест Telegram из скринера накопления · {now_et_str('%H:%M ET')}"):
            st.success("Тест отправлен.")
        else:
            st.error("Telegram не отправился. Проверь токен и chat_id.")
    if not telegram_configured:
        st.caption("Тест недоступен: нет TELEGRAM_TOKEN или TELEGRAM_CHAT_ID.")
    auto_scan = st.toggle("Авто-скан", value=False)
    auto_interval = st.select_slider(
        "Интервал",
        options=[5, 10, 15, 30, 60],
        value=15,
        format_func=lambda value: f"{value} мин",
        disabled=not auto_scan,
    )
    if st.button("Сбросить повторы Telegram", use_container_width=True):
        st.session_state.notified_signals = set()
        st.success("Повторы сброшены.")


# ── AUTO REFRESH ──────────────────────────────────────────────────
if auto_scan and st_autorefresh is not None:
    st_autorefresh(interval=auto_interval * 60 * 1000, key="accumulation_autorefresh")
elif auto_scan and st_autorefresh is None:
    st.warning("Для авто-обновления нужен пакет streamlit-autorefresh.")


# ── MAIN UI ───────────────────────────────────────────────────────
status_kind, status_text = get_market_status()
status_tone = {"success": "green", "warning": "amber", "info": "blue"}.get(status_kind, "")

cfg = ScanConfig(
    channel_days=channel_days,
    max_channel_width_pct=max_channel_width_pct,
    price_basis=price_basis,
    require_price_break=require_price_break,
    allow_volume_alert_inside_channel=allow_volume_alert_inside_channel,
    breakout_buffer_pct=breakout_buffer_pct,
    directions=directions,
    volume_baseline=volume_baseline,
    min_volume_mult=min_volume_mult,
    min_channel_avg_volume=int(min_channel_avg_volume),
    min_dollar_volume=int(min_dollar_volume),
    max_gap_pct=max_gap_pct,
    max_stale_days=max_stale_days,
    min_price=min_price,
    max_price=max_price,
    feed=feed_label,
)

telegram_ready = bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)
telegram_tone = "green" if send_alerts and telegram_ready else ("red" if send_alerts else "amber")
telegram_label = "готов" if send_alerts and telegram_ready else ("нет секрета" if send_alerts else "выкл")

st.markdown(
    f"""
    <div class="desk-header">
        <div>
            <div class="desk-title">Скринер накопления</div>
            <div class="desk-subtitle">Полный рынок · узкий канал · выход или ранний всплеск объёма</div>
        </div>
        <div class="desk-chipbar">
            {chip("Рынок", status_text, status_tone)}
            {chip("Время ET", now_et_str("%H:%M"), "blue")}
            {chip("Телеграм", telegram_label, telegram_tone)}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

setup_chips = "".join(
    [
        chip("Биржа", exchange),
        chip("Лимит акций", max_tickers),
        chip("Цена", f"${min_price:g}-${max_price:g}"),
        chip("Канал", f"{cfg.channel_days} дней / {cfg.max_channel_width_pct:g}%"),
        chip("Расчёт", "High/Low: вся свеча" if cfg.price_basis == "HIGH_LOW" else "Close: закрытия"),
        chip("Гэп", f"{cfg.max_gap_pct:g}%"),
        chip("Свежесть", f"{cfg.max_stale_days}д"),
        chip("Сигнал", "Пробой + объём" if cfg.require_price_break else "Пробой или ранний объём"),
        chip("Буфер", f"{cfg.breakout_buffer_pct:g}%"),
        chip("Объём", f"{cfg.volume_baseline} ({'макс.' if cfg.volume_baseline == 'MAX' else 'средн.'}) x{cfg.min_volume_mult:g}"),
        chip("Фид", cfg.feed.upper(), "amber" if cfg.feed == "iex" else "green"),
        chip("Долларовый объём", f"${cfg.min_dollar_volume:,}"),
        chip("Страница", page_num),
        chip("Маршрут", "авто-дальше" if advance_page_after_scan else "ручной"),
    ]
)
st.markdown(f'<div class="desk-chipbar">{setup_chips}</div>', unsafe_allow_html=True)

if yf is None and source_mode != "Alpaca only":
    st.warning('yfinance не установлен. Используй режим "Только Alpaca" или установи пакет: pip install yfinance')
if send_alerts and not telegram_ready:
    st.warning(
        "Telegram включён, но TELEGRAM_TOKEN или TELEGRAM_CHAT_ID не найдены в Streamlit secrets. "
        "В таком режиме уведомления в бот отправляться не будут."
    )

m1, m2, m3, m4 = st.columns(4)
m1.metric("Проверено", st.session_state.stats["checked"])
m2.metric("Сигналов", st.session_state.stats["signals"])
m3.metric("Сохранено", len(st.session_state.results))
m4.metric("Прогонов", st.session_state.auto_count)

route_stop_reached = bool(auto_scan and stop_after_cycles > 0 and st.session_state.market_cycles_done >= stop_after_cycles)
route_hint = f"страница {page_num}"
if st.session_state.last_route_pages:
    route_hint = (
        f"следующая страница {page_num}/{st.session_state.last_route_pages} · "
        f"кругов пройдено {st.session_state.market_cycles_done}"
    )

if auto_scan and route_stop_reached:
    should_auto_run = False
    auto_text = f"Авто-скан остановлен после {st.session_state.market_cycles_done} кругов · {route_hint}"
elif auto_scan:
    current = now_et()
    if st.session_state.auto_last_run:
        elapsed_sec = int((current - st.session_state.auto_last_run).total_seconds())
        remaining = max(0, auto_interval * 60 - elapsed_sec)
        should_auto_run = elapsed_sec >= auto_interval * 60
        auto_text = (
            f"Авто-скан: каждые {auto_interval} мин · последний {elapsed_sec // 60} мин назад · "
            f"следующий через {remaining // 60} мин · {route_hint}"
        )
    else:
        should_auto_run = True
        auto_text = f"Авто-скан: каждые {auto_interval} мин · первый запуск ожидается · {route_hint}"
else:
    should_auto_run = False
    auto_text = f"Авто-скан: выключен · {route_hint}"

st.markdown(
    f"""
    <div class="desk-panel">
        <div class="desk-panel-title">Состояние скана</div>
        <div class="desk-muted">{html.escape(auto_text)}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

button_col, clear_col = st.columns([1, 1])
with button_col:
    start_scan = st.button("Сканировать рынок", type="primary", use_container_width=True)
with clear_col:
    if st.button("Очистить результаты", use_container_width=True):
        st.session_state.results = []
        st.session_state.stats = {"checked": 0, "signals": 0}
        st.session_state.leader_analysis = None
        st.rerun()


if start_scan or (auto_scan and should_auto_run):
    all_tickers = get_nasdaq_tickers(exchange, max_scan_price)
    total_pages = total_pages_for(len(all_tickers), int(max_tickers))
    route_pages = effective_route_pages(total_pages, int(route_page_limit))
    scan_page = clamp_page(int(page_num), route_pages)
    page_start = (scan_page - 1) * int(max_tickers)
    page_end = page_start + int(max_tickers)
    ticker_infos = all_tickers[page_start:page_end]
    st.session_state.last_total_pages = total_pages
    st.session_state.last_route_pages = route_pages
    st.session_state.last_scan_page = scan_page

    st.markdown(
        f"""
        <div class="desk-panel">
            <div class="desk-panel-title">Рыночный список</div>
            <div class="desk-muted">загружено тикеров: {len(all_tickers)} · страница {scan_page}/{route_pages} · всего страниц: {total_pages} · проверяем: {len(ticker_infos)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if int(page_num) != scan_page:
        st.info(f"Страница {page_num} вне доступного маршрута. Сканирую ближайшую доступную страницу: {scan_page}/{route_pages}.")

    if not ticker_infos:
        st.error("Нет тикеров для сканирования.")
    else:
        progress_box = st.progress(0.0)
        status_box = st.empty()
        table_box = st.empty()

        hits = scan_market(
            ticker_infos=ticker_infos,
            cfg=cfg,
            source_mode=source_mode,
            progress_box=progress_box,
            status_box=status_box,
            table_box=table_box,
            send_alerts=send_alerts,
        )

        st.session_state.results = merge_results(hits, st.session_state.results)
        if analyze_leaders and st.session_state.results:
            status_box.caption("Разбираю лидеров: техника и новости...")
            st.session_state.leader_analysis = build_leader_analysis(st.session_state.results, news_candidate_count)
        else:
            st.session_state.leader_analysis = None

        st.session_state.auto_last_run = now_et()
        st.session_state.auto_count += 1
        progress_box.progress(1.0)

        if advance_page_after_scan:
            next_page, wrapped = next_route_page(scan_page, route_pages)
            st.session_state.scan_page = next_page
            st.session_state.sync_page_widget = True
            if wrapped:
                st.session_state.market_cycles_done += 1
                st.info(
                    f"Круг рынка завершён: {st.session_state.market_cycles_done}. "
                    f"Следующий скан начнётся со страницы {next_page}/{route_pages}."
                )
            else:
                st.info(f"Следующий скан начнётся со страницы {next_page}/{route_pages}.")

        if hits:
            status_box.success(f"Готово: найдено {len(hits)} сигналов.")
            if send_alerts:
                send_telegram(
                    f"✅ Скан накопления завершён · найдено {len(hits)} · "
                    f"проверено {len(ticker_infos)} · страница {scan_page}/{route_pages} · {now_et_str('%H:%M ET')}"
                )
                if send_leader_summary and st.session_state.leader_analysis:
                    send_telegram(telegram_leader_message(st.session_state.leader_analysis))
        else:
            status_box.info("Сигналов не найдено по текущим фильтрам.")

        if st.session_state.scan_errors:
            with st.expander("Диагностика"):
                st.write("\n".join(st.session_state.scan_errors))


if st.session_state.results:
    df_results = pd.DataFrame(st.session_state.results)
    if "_sig" in df_results.columns:
        up_mask = df_results["_sig"].eq(SIG_UP)
        down_mask = df_results["_sig"].eq(SIG_DOWN)
        early_mask = df_results["_sig"].eq(SIG_SURGE)
    else:
        up_mask = df_results["Сигнал"].isin(["ПРОБОЙ ВВЕРХ", "BREAKOUT UP"])
        down_mask = df_results["Сигнал"].isin(["ПРОБОЙ ВНИЗ", "BREAKDOWN DOWN"])
        early_mask = df_results["Сигнал"].isin(["РАННИЙ ОБЪЁМ В КАНАЛЕ", "VOLUME IN CHANNEL"])
    up_count = int(up_mask.sum())
    down_count = int(down_mask.sum())
    early_count = int(early_mask.sum())
    best_score = int(df_results["Балл"].max()) if "Балл" in df_results else 0

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Пробой вверх", up_count)
    r2.metric("Пробой вниз", down_count)
    r3.metric("Ранний объём", early_count)
    r4.metric("Лучший балл", best_score)

    if analyze_leaders:
        leader_analysis = st.session_state.leader_analysis
        if leader_analysis is None:
            with st.spinner("Разбираю лидеров по технике и новостям..."):
                leader_analysis = build_leader_analysis(st.session_state.results, news_candidate_count)
                st.session_state.leader_analysis = leader_analysis
        if leader_analysis:
            render_leader_analysis(leader_analysis)

    st.markdown('<div class="desk-section-title">Лента сигналов</div>', unsafe_allow_html=True)
    tab_all, tab_up, tab_down, tab_early = st.tabs(["Все", "Вверх", "Вниз", "Ранний объём"])
    with tab_all:
        st.dataframe(display_frame(st.session_state.results), use_container_width=True, hide_index=True)
    with tab_up:
        st.dataframe(display_frame(df_results[up_mask].to_dict("records")), use_container_width=True, hide_index=True)
    with tab_down:
        st.dataframe(display_frame(df_results[down_mask].to_dict("records")), use_container_width=True, hide_index=True)
    with tab_early:
        st.dataframe(display_frame(df_results[early_mask].to_dict("records")), use_container_width=True, hide_index=True)

    csv = display_frame(st.session_state.results).to_csv(index=False).encode("utf-8")
    st.download_button(
        "Скачать CSV",
        data=csv,
        file_name=f"accumulation_breakout_{now_et().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )
else:
    st.markdown(
        """
        <div class="desk-panel">
            <div class="desk-panel-title">Сигналов пока нет</div>
            <div class="desk-muted">Запусти скан или включи авто-скан, чтобы заполнить ленту сигналов.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
