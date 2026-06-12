from __future__ import annotations

import html
import base64
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

import altair as alt
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
st.set_page_config(page_title="PR Screener", page_icon="📊", layout="wide")


def apply_custom_theme() -> None:
    st.markdown(
        """
        <style>
            :root {
                --desk-bg: #eef2f6;
                --desk-ink: #101828;
                --desk-muted: #667085;
                --desk-line: #d0d5dd;
                --desk-panel: #ffffff;
                --desk-panel-soft: #f8fafc;
                --desk-green: #047857;
                --desk-red: #b42318;
                --desk-amber: #b54708;
                --desk-blue: #175cd3;
                --desk-navy: #182230;
                --desk-teal: #0e9384;
                --desk-soft: #f8fafc;
                --desk-shadow: 0 12px 32px rgba(16, 24, 40, 0.08);
                --desk-shadow-soft: 0 3px 12px rgba(16, 24, 40, 0.05);
            }

            .stApp {
                background: #eef2f6;
                color: var(--desk-ink);
            }

            header[data-testid="stHeader"],
            div[data-testid="stToolbar"],
            #MainMenu,
            footer {
                display: none !important;
                visibility: hidden;
                height: 0 !important;
                min-height: 0 !important;
            }

            section[data-testid="stSidebar"] {
                background: #fbfcfe;
                border-right: 1px solid var(--desk-line);
                box-shadow: 10px 0 30px rgba(16, 24, 40, 0.04);
            }

            section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
                color: var(--desk-muted);
            }

            section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
                gap: 0.55rem;
            }

            .block-container {
                padding-top: 0.85rem;
                padding-bottom: 2rem;
                max-width: 1680px;
            }

            h1, h2, h3 {
                letter-spacing: 0;
            }

            div[data-testid="stMetric"] {
                background: var(--desk-panel);
                border: 1px solid var(--desk-line);
                border-radius: 8px;
                padding: 0.7rem 0.85rem;
                box-shadow: var(--desk-shadow-soft);
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
                align-items: stretch;
                justify-content: space-between;
                gap: 1.2rem;
                margin-bottom: 0.7rem;
                padding: 1.05rem 1.2rem;
                border: 1px solid var(--desk-line);
                border-top: 4px solid var(--desk-navy);
                border-radius: 8px;
                background: #ffffff;
                box-shadow: var(--desk-shadow);
            }

            .desk-title {
                font-size: 1.78rem;
                font-weight: 800;
                line-height: 1.15;
                margin: 0;
                color: var(--desk-navy);
            }

            .desk-subtitle {
                margin-top: 0.25rem;
                color: var(--desk-muted);
                font-size: 0.92rem;
            }

            .desk-statusbar {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                align-items: stretch;
                justify-content: flex-end;
                min-width: 0;
                max-width: 100%;
            }

            .desk-header > div,
            .base-results-bar > div,
            .desk-empty-panel > div,
            .pattern-chart-head > div {
                min-width: 0;
            }

            .desk-chipbar {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                margin: 0;
            }

            .desk-chip {
                display: inline-flex;
                flex-direction: column;
                align-items: flex-start;
                justify-content: center;
                gap: 0.18rem;
                border: 1px solid var(--desk-line);
                border-left: 3px solid #98a2b3;
                border-radius: 8px;
                background: #ffffff;
                color: var(--desk-muted);
                min-height: 44px;
                min-width: 92px;
                max-width: 100%;
                padding: 0.42rem 0.62rem;
                font-size: 0.72rem;
                line-height: 1.1;
                box-shadow: 0 1px 2px rgba(16, 24, 40, 0.03);
            }

            .desk-chip-label {
                color: var(--desk-muted);
                font-size: 0.64rem;
                font-weight: 760;
                letter-spacing: 0.04em;
                text-transform: uppercase;
                white-space: nowrap;
            }

            .desk-chip-value {
                color: var(--desk-ink);
                font-size: 0.82rem;
                font-weight: 780;
                line-height: 1.15;
                max-width: 220px;
                overflow-wrap: anywhere;
                white-space: normal;
            }

            .desk-chip.green { border-color: #a6f4c5; border-left-color: var(--desk-green); background: #ecfdf3; }
            .desk-chip.red { border-color: #fecdca; border-left-color: var(--desk-red); background: #fff1f0; }
            .desk-chip.amber { border-color: #fedf89; border-left-color: var(--desk-amber); background: #fffaeb; }
            .desk-chip.blue { border-color: #b2ddff; border-left-color: var(--desk-blue); background: #eff8ff; }

            .desk-filter-board {
                background: #ffffff;
                border: 1px solid var(--desk-line);
                border-radius: 8px;
                padding: 0.75rem 0.85rem 0.85rem;
                margin: 0 0 0.85rem;
                box-shadow: var(--desk-shadow-soft);
            }

            .desk-filter-title {
                color: var(--desk-muted);
                font-size: 0.7rem;
                font-weight: 800;
                letter-spacing: 0.06em;
                text-transform: uppercase;
                margin-bottom: 0.52rem;
            }

            .sidebar-brand {
                background: #ffffff;
                border: 1px solid var(--desk-line);
                border-top: 3px solid var(--desk-navy);
                border-radius: 8px;
                padding: 0.9rem 0.95rem;
                margin: 0.25rem 0 1rem;
                box-shadow: var(--desk-shadow-soft);
            }

            .sidebar-brand-title {
                color: var(--desk-navy);
                font-size: 1rem;
                font-weight: 820;
                line-height: 1.15;
            }

            .sidebar-brand-subtitle {
                color: var(--desk-muted);
                font-size: 0.78rem;
                line-height: 1.35;
                margin-top: 0.3rem;
            }

            .desk-section-title {
                font-size: 0.82rem;
                text-transform: uppercase;
                color: var(--desk-muted);
                letter-spacing: 0.05em;
                font-weight: 800;
                margin: 0.55rem 0 0.35rem;
            }

            .desk-panel {
                background: var(--desk-panel);
                border: 1px solid var(--desk-line);
                border-radius: 8px;
                padding: 0.95rem 1rem;
                margin-bottom: 0.8rem;
                box-shadow: var(--desk-shadow-soft);
            }

            .desk-panel-title {
                color: var(--desk-navy);
                font-weight: 800;
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

            .pattern-chart-card {
                background: #ffffff;
                border: 1px solid var(--desk-line);
                border-top: 3px solid var(--desk-blue);
                border-radius: 8px;
                padding: 0.95rem;
                margin-bottom: 1.05rem;
                box-shadow: var(--desk-shadow);
            }

            .pattern-chart-head {
                display: flex;
                flex-wrap: wrap;
                justify-content: space-between;
                gap: 0.75rem;
                align-items: flex-start;
                margin-bottom: 0.65rem;
            }

            .pattern-chart-symbol {
                color: var(--desk-navy);
                font-size: 1.35rem;
                font-weight: 820;
                line-height: 1.1;
            }

            .pattern-chart-meta {
                color: #344054;
                font-size: 0.78rem;
                line-height: 1.25;
                text-align: right;
                overflow-wrap: anywhere;
                background: var(--desk-panel-soft);
                border: 1px solid #e4e7ec;
                border-radius: 8px;
                padding: 0.42rem 0.55rem;
            }

            .pattern-chart-stats {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.45rem;
                margin-bottom: 0.65rem;
            }

            .pattern-chart-stat {
                background: var(--desk-soft);
                border: 1px solid #e4e7ec;
                border-radius: 8px;
                padding: 0.48rem 0.55rem;
                min-width: 0;
            }

            .pattern-chart-stat span {
                display: block;
                color: var(--desk-muted);
                font-size: 0.66rem;
                font-weight: 700;
                letter-spacing: 0.04em;
                text-transform: uppercase;
                overflow-wrap: anywhere;
            }

            .pattern-chart-stat strong {
                display: block;
                color: var(--desk-navy);
                font-size: 0.9rem;
                font-weight: 760;
                line-height: 1.15;
                overflow-wrap: anywhere;
            }

            .pattern-chart-card img {
                display: block;
                width: 100%;
                aspect-ratio: 1.35 / 1;
                object-fit: contain;
                border: 1px solid #eef2f6;
                border-radius: 8px;
                background: #ffffff;
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
                box-shadow: var(--desk-shadow);
            }

            div[data-testid="stDataFrame"] [role="columnheader"] {
                background: #f8fafc;
                color: var(--desk-navy);
                font-weight: 800;
            }

            .base-results-bar {
                display: flex;
                justify-content: space-between;
                align-items: flex-end;
                gap: 1rem;
                margin: 0.25rem 0 0.75rem;
                padding: 0.95rem 1rem;
                border: 1px solid var(--desk-line);
                border-top: 3px solid var(--desk-navy);
                border-radius: 8px;
                background: #ffffff;
                box-shadow: var(--desk-shadow);
            }

            .base-results-title {
                color: var(--desk-navy);
                font-size: 1.24rem;
                font-weight: 820;
                line-height: 1.15;
            }

            .base-results-subtitle {
                color: var(--desk-muted);
                font-size: 0.82rem;
                margin-top: 0.18rem;
            }

            .base-results-stats {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                justify-content: flex-end;
            }

            .base-results-stats .desk-chip-value {
                max-width: 230px;
            }

            .desk-empty-panel {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 1rem;
                background: #ffffff;
                border: 1px solid var(--desk-line);
                border-top: 3px solid var(--desk-navy);
                border-radius: 8px;
                padding: 1rem 1.1rem;
                box-shadow: var(--desk-shadow-soft);
            }

            .desk-empty-title {
                color: var(--desk-navy);
                font-size: 1.05rem;
                font-weight: 820;
                line-height: 1.2;
            }

            @media (max-width: 900px) {
                .desk-header,
                .base-results-bar,
                .desk-empty-panel {
                    align-items: flex-start;
                    flex-direction: column;
                }

                .base-results-stats {
                    justify-content: flex-start;
                }

                .pattern-chart-stats {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }
            }

            @media (max-width: 600px) {
                .block-container {
                    padding-left: 0.7rem;
                    padding-right: 0.7rem;
                }

                .desk-title {
                    font-size: 1.35rem;
                }

                .desk-statusbar,
                .base-results-stats {
                    width: 100%;
                    justify-content: flex-start;
                }

                .desk-chip {
                    flex: 1 1 130px;
                    min-width: 0;
                }

                .desk-chip-value {
                    max-width: 100%;
                }

                .pattern-chart-meta {
                    width: 100%;
                    text-align: left;
                }

                .pattern-chart-stats {
                    grid-template-columns: 1fr;
                }
            }

            div.stButton > button[kind="primary"] {
                background: var(--desk-blue);
                border-color: var(--desk-blue);
                color: #ffffff;
                border-radius: 8px;
                min-height: 2.7rem;
                font-weight: 780;
            }

            div.stButton > button[kind="primary"]:hover {
                background: #1849a9;
                border-color: #1849a9;
                color: #ffffff;
            }

            div.stButton > button {
                border-radius: 8px;
                min-height: 2.7rem;
                font-weight: 720;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def chip(label: str, value: Any, tone: str = "") -> str:
    tone_class = f" {tone}" if tone else ""
    return (
        f'<span class="desk-chip{tone_class}">'
        f'<span class="desk-chip-label">{html.escape(label)}</span>'
        f'<span class="desk-chip-value">{html.escape(str(value))}</span>'
        f"</span>"
    )


apply_custom_theme()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("accumulation_breakout")

MARKET_TZ = ZoneInfo("America/New_York")
ALPACA_BASE = "https://data.alpaca.markets"
DATA_TIMEOUT_SEC = 15
NASDAQ_TIMEOUT_SEC = 20
BATCH_SIZE = 120
ALPACA_SIP_DELAY_MINUTES = 16
MAX_BARS_PAGES = 25
AUTO_SCAN_MARKET_LIMIT = 10_000

DATA_SOURCE_AUTO = "AUTO_ALPACA_SIP_YAHOO"
DATA_SOURCE_ALPACA_SIP = "ALPACA_SIP_DELAYED"
DATA_SOURCE_YAHOO = "YAHOO"
DATA_SOURCE_LABELS = {
    DATA_SOURCE_AUTO: "Alpaca SIP delayed → Yahoo",
    DATA_SOURCE_ALPACA_SIP: "Alpaca SIP delayed",
    DATA_SOURCE_YAHOO: "Yahoo Finance",
}

SIG_UP = "BREAKOUT_UP"
SIG_DOWN = "BREAKDOWN"
SIG_SURGE = "VOLUME_SURGE"
SIG_BASE = "BASE_VOLUME_EXPLOSION"
SIG_VCP = "VCP_SQUEEZE"
SIG_SPRING = "SPRING_REVERSAL"

SCANNER_BASE = "BASE_VOLUME"
SCANNER_VCP = "VCP_SQUEEZE"
SCANNER_SPRING = "SPRING_REVERSAL"

SCANNER_LABELS = {
    SCANNER_BASE: "Взрыв из базы",
    SCANNER_VCP: "VCP-сжатие",
    SCANNER_SPRING: "Spring-отскок",
}
SCANNER_HELP = {
    SCANNER_BASE: (
        "Ищет твой старый паттерн: сегодняшнее открытие внутри вчерашней свечи, "
        "а сегодняшний объём выше максимального объёма среди предыдущих свечей."
    ),
    SCANNER_VCP: (
        "Ищет сжатие перед движением: диапазон свечей постепенно становится уже, "
        "объём сохнет, цена находится близко к верхней границе базы."
    ),
    SCANNER_SPRING: (
        "Ищет ложный прокол поддержки: цена сходила ниже важного минимума, "
        "но закрылась обратно выше поддержки на повышенном объёме."
    ),
}
SCANNER_SUBTITLES = {
    SCANNER_BASE: "Полный рынок · открытие внутри вчерашней свечи · объём выше всей базы",
    SCANNER_VCP: "Полный рынок · сжатие диапазона · сухой объём · цена рядом с верхом базы",
    SCANNER_SPRING: "Полный рынок · прокол поддержки · возврат над уровень · объёмный отскок",
}

SIGNAL_LABELS = {
    SIG_UP: "ПРОБОЙ ВВЕРХ",
    SIG_DOWN: "ПРОБОЙ ВНИЗ",
    SIG_SURGE: "РАННИЙ ОБЪЁМ В КАНАЛЕ",
    SIG_BASE: "ВЗРЫВ ОБЪЁМА ИЗ БАЗЫ",
    SIG_VCP: "VCP-СЖАТИЕ",
    SIG_SPRING: "SPRING ОТ ДНА",
}
SIGNAL_ICONS = {SIG_UP: "🟢", SIG_DOWN: "🔴", SIG_SURGE: "🔥", SIG_BASE: "⚡", SIG_VCP: "🌀", SIG_SPRING: "🌱"}
SIGNAL_SHORT_LABELS = {
    SIG_UP: "Пробой вверх",
    SIG_DOWN: "Пробой вниз",
    SIG_SURGE: "Ранний объём",
    SIG_BASE: "Взрыв базы",
    SIG_VCP: "VCP-сжатие",
    SIG_SPRING: "Spring от дна",
}

DISPLAY_COLS = [
    "Тикер",
    "Сигнал",
    "Цена",
    "RVOL",
    "Движение %",
    "Объём",
    "Долларовый объём",
    "Капитализация",
    "Время",
]

BASE_PATTERN_DISPLAY_COLS = DISPLAY_COLS


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
    scanner_mode: str = SCANNER_BASE
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

    base_impulse_enabled: bool = True
    base_impulse_days: int = 10
    base_volume_mult: float = 10.0
    base_impulse_only: bool = False

    max_gap_pct: float = 8.0
    max_stale_days: int = 5
    min_price: float = 0.5
    max_price: float = 20.0

    vcp_days: int = 45
    vcp_max_base_width_pct: float = 35.0
    vcp_max_recent_width_pct: float = 12.0
    vcp_min_compression_pct: float = 25.0
    vcp_near_high_pct: float = 8.0
    vcp_dry_volume_ratio: float = 0.85

    spring_support_days: int = 60
    spring_low_days: int = 120
    spring_break_pct: float = 1.0
    spring_reclaim_pct: float = 0.0
    spring_close_position_pct: float = 60.0
    spring_volume_mult: float = 1.2
    spring_max_from_low_pct: float = 35.0


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


def parse_market_cap(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().upper().replace("$", "").replace(",", "")
    if not text or text in {"N/A", "NA", "NONE", "-", "—"}:
        return None

    multiplier = 1.0
    suffix = text[-1]
    if suffix in {"K", "M", "B", "T"}:
        text = text[:-1].strip()
        multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "T": 1_000_000_000_000}[suffix]

    try:
        number = float(text)
    except ValueError:
        return None
    return number * multiplier if number > 0 else None


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
                    "market_cap": parse_market_cap(
                        row.get("marketCap")
                        or row.get("marketcap")
                        or row.get("market_cap")
                        or row.get("market capitalization")
                    ),
                }
            )

    if tickers:
        return tickers

    fallback = ["SBET", "PLTR", "SOUN", "QBTS", "OPEN", "SOFI", "HIMS", "PLUG", "RIVN", "LCID"]
    return [{"ticker": ticker, "exchange": "US", "name": "", "price_api": 0.0} for ticker in fallback]


# ── DATA SOURCES ──────────────────────────────────────────────────
def alpaca_sip_end_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=ALPACA_SIP_DELAY_MINUTES)


def rfc3339_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@st.cache_data(ttl=60, show_spinner=False)
def fetch_alpaca_sip_delayed_batch(symbols: tuple[str, ...], days: int) -> dict[str, pd.DataFrame]:
    if not ALPACA_KEY or not ALPACA_SECRET or not symbols:
        return {}

    end_dt = alpaca_sip_end_utc()
    start_dt = end_dt - timedelta(days=max(90, int(days) * 6))
    params: dict[str, Any] = {
        "symbols": ",".join(symbol.upper() for symbol in symbols),
        "timeframe": "1Day",
        "start": rfc3339_utc(start_dt),
        "end": rfc3339_utc(end_dt),
        "limit": 10000,
        "adjustment": "split",
        "feed": "sip",
        "sort": "asc",
    }

    bars_by_symbol: dict[str, list[dict[str, Any]]] = {symbol.upper(): [] for symbol in symbols}
    page_token = None
    try:
        for _ in range(MAX_BARS_PAGES):
            request_params = params.copy()
            if page_token:
                request_params["page_token"] = page_token
            resp = requests.get(
                f"{ALPACA_BASE}/v2/stocks/bars",
                headers=ALPACA_HEADERS,
                params=request_params,
                timeout=DATA_TIMEOUT_SEC,
            )
            if resp.status_code in {401, 403}:
                LOGGER.info("Alpaca SIP delayed auth/permission failed: %s %s", resp.status_code, resp.text[:300])
                return {}
            resp.raise_for_status()
            payload = resp.json()
            raw_bars = payload.get("bars") or {}
            if isinstance(raw_bars, dict):
                for symbol, rows in raw_bars.items():
                    symbol_key = str(symbol).upper()
                    if isinstance(rows, list):
                        bars_by_symbol.setdefault(symbol_key, []).extend(rows)
            page_token = payload.get("next_page_token")
            if not page_token:
                break
        if page_token:
            LOGGER.info("Alpaca SIP delayed pagination stopped after %s pages.", MAX_BARS_PAGES)
    except Exception as exc:
        LOGGER.info("Alpaca SIP delayed batch failed: %s", exc)
        return {}

    out: dict[str, pd.DataFrame] = {}
    for symbol, rows in bars_by_symbol.items():
        if not rows:
            continue
        normalized = normalize_ohlcv(pd.DataFrame(rows), "Alpaca SIP delayed")
        if normalized is not None and len(normalized) >= days + 2:
            out[symbol] = normalized
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


@st.cache_data(ttl=60, show_spinner=False)
def fetch_yahoo_batch(symbols: tuple[str, ...], days: int) -> dict[str, pd.DataFrame]:
    if yf is None or not symbols:
        return {}

    period = "90d" if days <= 20 else "6mo"
    try:
        df = yf.download(
            tickers=list(symbols),
            period=period,
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
            timeout=DATA_TIMEOUT_SEC,
        )
    except Exception as exc:
        LOGGER.info("Yahoo batch failed: %s", exc)
        return {}

    if df is None or df.empty:
        return {}

    out: dict[str, pd.DataFrame] = {}
    symbols_upper = [symbol.upper() for symbol in symbols]
    if isinstance(df.columns, pd.MultiIndex):
        level0 = {str(value).upper() for value in df.columns.get_level_values(0)}
        level1 = {str(value).upper() for value in df.columns.get_level_values(1)}
        for symbol in symbols_upper:
            candidate = None
            if symbol in level0:
                candidate = df[symbol]
            elif symbol in level1:
                candidate = df.xs(symbol, axis=1, level=1)
            normalized = normalize_ohlcv(candidate, "Yahoo Finance")
            if normalized is not None and len(normalized) >= days + 2:
                out[symbol] = normalized
        return out

    if len(symbols_upper) == 1:
        normalized = normalize_ohlcv(df, "Yahoo Finance")
        if normalized is not None and len(normalized) >= days + 2:
            out[symbols_upper[0]] = normalized
    return out


def fetch_daily_history(ticker: str, days: int, data_source: str) -> pd.DataFrame | None:
    symbol = ticker.upper()
    if data_source in {DATA_SOURCE_ALPACA_SIP, DATA_SOURCE_AUTO}:
        alpaca_rows = fetch_alpaca_sip_delayed_batch((symbol,), days)
        history = alpaca_rows.get(symbol)
        if history is not None:
            return history

    if data_source in {DATA_SOURCE_YAHOO, DATA_SOURCE_AUTO}:
        return fetch_yahoo_daily(symbol, days)

    return None


def required_history_days(cfg: ScanConfig) -> int:
    if cfg.scanner_mode == SCANNER_VCP:
        return max(int(cfg.vcp_days), 30)
    if cfg.scanner_mode == SCANNER_SPRING:
        return max(int(cfg.spring_support_days), int(cfg.spring_low_days), 60)
    return max(int(cfg.base_impulse_days), 5)


def load_bars(
    ticker_infos: list[dict[str, Any]],
    cfg: ScanConfig,
    data_source: str,
    progress_box: Any,
    status_box: Any,
) -> dict[str, pd.DataFrame]:
    symbols = [str(item["ticker"]).upper() for item in ticker_infos]
    bars: dict[str, pd.DataFrame] = {}
    history_days = required_history_days(cfg)

    if data_source in {DATA_SOURCE_ALPACA_SIP, DATA_SOURCE_AUTO} and not (ALPACA_KEY and ALPACA_SECRET):
        status_box.caption("Alpaca SIP delayed недоступен: нет ALPACA_KEY / ALPACA_SECRET.")
        if data_source == DATA_SOURCE_ALPACA_SIP:
            return bars

    if data_source in {DATA_SOURCE_YAHOO, DATA_SOURCE_AUTO} and yf is None:
        status_box.caption("Yahoo Finance недоступен: пакет yfinance не установлен.")
        if data_source == DATA_SOURCE_YAHOO:
            return bars

    batches = list(chunks(symbols, BATCH_SIZE))
    if data_source in {DATA_SOURCE_ALPACA_SIP, DATA_SOURCE_AUTO} and ALPACA_KEY and ALPACA_SECRET:
        for idx, batch in enumerate(batches, start=1):
            status_box.caption(
                f"Загружаю Alpaca SIP delayed ({ALPACA_SIP_DELAY_MINUTES} мин) · "
                f"пачка {idx}/{len(batches)} · готово: {len(bars)}"
            )
            bars.update(fetch_alpaca_sip_delayed_batch(tuple(batch), history_days))
            progress_box.progress(0.55 * idx / max(len(batches), 1))

        if data_source == DATA_SOURCE_ALPACA_SIP:
            progress_box.progress(0.7)
            return bars

    missing_symbols = [symbol for symbol in symbols if symbol not in bars]
    if data_source == DATA_SOURCE_AUTO and not missing_symbols:
        progress_box.progress(0.7)
        return bars

    if data_source not in {DATA_SOURCE_YAHOO, DATA_SOURCE_AUTO}:
        progress_box.progress(0.7)
        return bars

    if yf is None:
        progress_box.progress(0.7)
        return bars

    yahoo_batches = list(chunks(missing_symbols if data_source == DATA_SOURCE_AUTO else symbols, BATCH_SIZE))
    for idx, batch in enumerate(yahoo_batches, start=1):
        status_box.caption(
            f"Загружаю Yahoo Finance · пачка {idx}/{len(yahoo_batches)} · "
            f"готово: {len(bars)}"
        )
        bars.update(fetch_yahoo_batch(tuple(batch), history_days))
        progress_box.progress(0.55 + 0.15 * idx / max(len(yahoo_batches), 1))

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


@dataclass(frozen=True)
class BaseImpulse:
    low: float
    high: float
    width_pct: float
    vol_max: float
    vol_avg: float
    max_gap_pct: float
    volume_mult: float
    move_pct: float
    body_pct: float


@dataclass(frozen=True)
class VcpSetup:
    low: float
    high: float
    base_width_pct: float
    recent_width_pct: float
    first_width_pct: float
    dry_volume_ratio: float
    current_volume_ratio: float
    distance_to_high_pct: float
    move_pct: float


@dataclass(frozen=True)
class SpringSetup:
    support: float
    latest_low: float
    support_range_pct: float
    break_pct: float
    reclaim_pct: float
    close_position_pct: float
    volume_mult: float
    from_low_pct: float
    move_pct: float


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


def build_base_impulse(df: pd.DataFrame, cfg: ScanConfig) -> BaseImpulse | None:
    if not cfg.base_impulse_enabled:
        return None

    lookback = int(cfg.base_impulse_days)
    if lookback < 3 or len(df) < lookback + 2:
        return None

    window = df.iloc[-(lookback + 1) : -1].copy()
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    latest_open = float(latest["Open"])
    latest_close = float(latest["Close"])
    latest_volume = float(latest["Volume"])
    if latest_open <= 0 or latest_close <= 0 or latest_volume <= 0:
        return None

    prev_low = float(prev["Low"])
    prev_high = float(prev["High"])
    if prev_low <= 0 or prev_high <= prev_low:
        return None

    if not (prev_low <= latest_open <= prev_high):
        return None

    volumes = pd.to_numeric(window["Volume"], errors="coerce").dropna()
    if len(volumes) < lookback or (volumes < 0).any():
        return None
    vol_max = float(volumes.max())
    vol_avg = float(volumes.mean())
    if vol_max <= 0:
        return None

    volume_mult = latest_volume / vol_max
    if latest_volume <= vol_max * cfg.base_volume_mult:
        return None

    prev_close = float(prev["Close"])
    latest_gap_pct = (latest_open - prev_close) / prev_close * 100 if prev_close > 0 else 0.0
    body_pct = abs(latest_close - latest_open) / latest_open * 100
    move_pct = (latest_close - latest_open) / latest_open * 100
    return BaseImpulse(
        low=prev_low,
        high=prev_high,
        width_pct=(prev_high - prev_low) / prev_low * 100,
        vol_max=vol_max,
        vol_avg=vol_avg,
        max_gap_pct=abs(latest_gap_pct),
        volume_mult=volume_mult,
        move_pct=move_pct,
        body_pct=body_pct,
    )


def pct_range(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    low = float(pd.to_numeric(frame["Low"], errors="coerce").min())
    high = float(pd.to_numeric(frame["High"], errors="coerce").max())
    if low <= 0 or high <= low:
        return 0.0
    return (high - low) / low * 100


def build_vcp_setup(df: pd.DataFrame, cfg: ScanConfig) -> VcpSetup | None:
    lookback = int(cfg.vcp_days)
    if lookback < 30 or len(df) < lookback + 2:
        return None

    window = df.tail(lookback).copy()
    if len(window) < lookback:
        return None

    third_size = len(window) // 3
    thirds = [
        window.iloc[:third_size],
        window.iloc[third_size : third_size * 2],
        window.iloc[third_size * 2 :],
    ]
    thirds = [part for part in thirds if not part.empty]
    if len(thirds) != 3:
        return None

    first_width = pct_range(thirds[0])
    recent_width = pct_range(thirds[-1])
    base_width = pct_range(window)
    if first_width <= 0 or recent_width <= 0 or base_width <= 0:
        return None
    if base_width > cfg.vcp_max_base_width_pct:
        return None
    if recent_width > cfg.vcp_max_recent_width_pct:
        return None

    required_recent_width = first_width * (1 - cfg.vcp_min_compression_pct / 100)
    if recent_width > required_recent_width:
        return None

    close = float(window.iloc[-1]["Close"])
    prev_close = float(df.iloc[-2]["Close"])
    base_low = float(window["Low"].min())
    base_high = float(window["High"].max())
    if close <= 0 or prev_close <= 0 or base_high <= base_low:
        return None

    distance_to_high = (base_high - close) / base_high * 100
    if distance_to_high < -2.0 or distance_to_high > cfg.vcp_near_high_pct:
        return None

    older_volume = pd.to_numeric(pd.concat([thirds[0]["Volume"], thirds[1]["Volume"]]), errors="coerce")
    recent_volume = pd.to_numeric(thirds[-1]["Volume"], errors="coerce")
    older_avg = float(older_volume[older_volume > 0].mean()) if not older_volume.empty else 0.0
    recent_avg = float(recent_volume[recent_volume > 0].mean()) if not recent_volume.empty else 0.0
    if older_avg <= 0 or recent_avg <= 0:
        return None

    dry_ratio = recent_avg / older_avg
    if dry_ratio > cfg.vcp_dry_volume_ratio:
        return None

    current_volume = float(window.iloc[-1]["Volume"])
    current_volume_ratio = current_volume / recent_avg if recent_avg > 0 else 0.0
    move_pct = (close - prev_close) / prev_close * 100
    return VcpSetup(
        low=base_low,
        high=base_high,
        base_width_pct=base_width,
        recent_width_pct=recent_width,
        first_width_pct=first_width,
        dry_volume_ratio=dry_ratio,
        current_volume_ratio=current_volume_ratio,
        distance_to_high_pct=distance_to_high,
        move_pct=move_pct,
    )


def build_spring_setup(df: pd.DataFrame, cfg: ScanConfig) -> SpringSetup | None:
    support_days = int(cfg.spring_support_days)
    low_days = int(cfg.spring_low_days)
    required = max(support_days, low_days)
    if support_days < 20 or len(df) < required + 2:
        return None

    support_window = df.iloc[-(support_days + 1) : -1].copy()
    if len(support_window) < support_days:
        return None

    latest = df.iloc[-1]
    prev_close = float(df.iloc[-2]["Close"])
    latest_open = float(latest["Open"])
    latest_high = float(latest["High"])
    latest_low = float(latest["Low"])
    latest_close = float(latest["Close"])
    latest_volume = float(latest["Volume"])
    if min(latest_open, latest_high, latest_low, latest_close, prev_close) <= 0 or latest_volume <= 0:
        return None
    if latest_high <= latest_low:
        return None

    support = float(support_window["Low"].min())
    support_high = float(support_window["High"].max())
    if support <= 0 or support_high <= support:
        return None

    break_pct = (support - latest_low) / support * 100
    if break_pct < cfg.spring_break_pct:
        return None

    reclaim_pct = (latest_close - support) / support * 100
    if reclaim_pct < cfg.spring_reclaim_pct:
        return None

    close_position = (latest_close - latest_low) / (latest_high - latest_low) * 100
    if close_position < cfg.spring_close_position_pct:
        return None

    ref_volume = pd.to_numeric(support_window["Volume"], errors="coerce")
    ref_volume = ref_volume[ref_volume > 0]
    if ref_volume.empty:
        return None
    volume_ref = float(ref_volume.mean())
    volume_mult = latest_volume / volume_ref if volume_ref > 0 else 0.0
    if volume_mult < cfg.spring_volume_mult:
        return None

    long_window = df.tail(low_days).copy()
    long_low = float(long_window["Low"].min())
    from_low_pct = (latest_close - long_low) / long_low * 100 if long_low > 0 else 999.0
    if from_low_pct > cfg.spring_max_from_low_pct:
        return None

    move_pct = (latest_close - prev_close) / prev_close * 100
    support_range_pct = (support_high - support) / support * 100
    return SpringSetup(
        support=support,
        latest_low=latest_low,
        support_range_pct=support_range_pct,
        break_pct=break_pct,
        reclaim_pct=reclaim_pct,
        close_position_pct=close_position,
        volume_mult=volume_mult,
        from_low_pct=from_low_pct,
        move_pct=move_pct,
    )


def pattern_chart_data_uri(
    df: pd.DataFrame,
    lookback: int,
    band_low: float | None = None,
    band_high: float | None = None,
    band_label: str = "зона сигнала",
) -> str:
    chart_df = df.dropna(subset=["Open", "High", "Low", "Close"]).tail(max(lookback + 1, 14)).copy()
    if chart_df.empty:
        return ""

    width = 460
    height = 340
    pad_x = 28
    price_top = 18
    price_bottom = 222
    volume_top = 252
    volume_bottom = 315
    plot_w = width - pad_x * 2
    price_h = price_bottom - price_top
    volume_h = volume_bottom - volume_top

    chart_df["Volume"] = pd.to_numeric(chart_df["Volume"], errors="coerce").fillna(0)
    chart_df["Open"] = pd.to_numeric(chart_df["Open"], errors="coerce")
    chart_df["High"] = pd.to_numeric(chart_df["High"], errors="coerce")
    chart_df["Low"] = pd.to_numeric(chart_df["Low"], errors="coerce")
    chart_df["Close"] = pd.to_numeric(chart_df["Close"], errors="coerce")
    chart_df = chart_df.dropna(subset=["Open", "High", "Low", "Close"])
    if chart_df.empty:
        return ""

    plot_w = width - pad_x * 2

    lows = chart_df["Low"]
    highs = chart_df["High"]
    min_price = float(lows.min())
    max_price = float(highs.max())
    if band_low and band_low > 0:
        min_price = min(min_price, float(band_low))
    if band_high and band_high > 0:
        max_price = max(max_price, float(band_high))
    if min_price <= 0 or max_price <= min_price:
        return ""

    def y_pos(value: float) -> float:
        return price_top + (max_price - value) / (max_price - min_price) * price_h

    max_volume = float(chart_df["Volume"].max())
    if max_volume <= 0:
        max_volume = 1.0

    def vol_y(value: float) -> float:
        return volume_bottom - value / max_volume * volume_h

    count = len(chart_df)
    step = plot_w / max(count - 1, 1)
    candle_w = max(5.0, min(11.0, step * 0.62))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" rx="8" fill="#ffffff"/>',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="8" fill="none" stroke="#d8dde6"/>',
        f'<line x1="{pad_x}" x2="{width - pad_x}" y1="{price_top}" y2="{price_top}" stroke="#edf2f7"/>',
        f'<line x1="{pad_x}" x2="{width - pad_x}" y1="{(price_top + price_bottom) / 2:.2f}" y2="{(price_top + price_bottom) / 2:.2f}" stroke="#edf2f7"/>',
        f'<line x1="{pad_x}" x2="{width - pad_x}" y1="{price_bottom}" y2="{price_bottom}" stroke="#edf2f7"/>',
        f'<line x1="{pad_x}" x2="{width - pad_x}" y1="{volume_bottom}" y2="{volume_bottom}" stroke="#edf2f7"/>',
        f'<text x="{pad_x}" y="{height - 12}" fill="#667085" font-size="11" font-family="Inter, Arial, sans-serif">цена / объём</text>',
        f'<text x="{width - pad_x}" y="{height - 12}" fill="#667085" font-size="11" font-family="Inter, Arial, sans-serif" text-anchor="end">{len(chart_df)} свечей</text>',
    ]

    if band_low is None or band_high is None:
        if len(chart_df) >= 2:
            prev = chart_df.iloc[-2]
            band_low = float(prev["Low"])
            band_high = float(prev["High"])

    if band_low is not None and band_high is not None and band_high > band_low > 0:
        band_y = y_pos(float(band_high))
        band_h = max(1.0, y_pos(float(band_low)) - band_y)
        parts.append(f'<rect x="{pad_x}" y="{band_y:.2f}" width="{plot_w}" height="{band_h:.2f}" rx="3" fill="#dbeafe" opacity="0.72"/>')
        parts.append(
            f'<text x="{pad_x + 6}" y="{max(price_top + 12, band_y - 5):.2f}" fill="#175cd3" '
            f'font-size="11" font-weight="700" font-family="Inter, Arial, sans-serif">{html.escape(band_label)}</text>'
        )

    prior_volumes = chart_df["Volume"].iloc[:-1]
    if not prior_volumes.empty and float(prior_volumes.max()) > 0:
        prior_max_y = vol_y(float(prior_volumes.max()))
        parts.append(
            f'<line x1="{pad_x}" x2="{width - pad_x}" y1="{prior_max_y:.2f}" y2="{prior_max_y:.2f}" '
            f'stroke="#667085" stroke-width="1.3" stroke-dasharray="5 4"/>'
        )

    for idx, row in enumerate(chart_df.itertuples(index=False), start=0):
        open_price = float(getattr(row, "Open"))
        high_price = float(getattr(row, "High"))
        low_price = float(getattr(row, "Low"))
        close_price = float(getattr(row, "Close"))
        volume = float(getattr(row, "Volume"))
        x = pad_x + idx * step
        color = "#047857" if close_price >= open_price else "#b42318"
        y_high = y_pos(high_price)
        y_low = y_pos(low_price)
        y_open = y_pos(open_price)
        y_close = y_pos(close_price)
        body_y = min(y_open, y_close)
        body_h = max(1.2, abs(y_close - y_open))
        stroke_w = 2.4 if idx == count - 1 else 1.5
        vol_top = vol_y(volume)
        vol_h = max(1.0, volume_bottom - vol_top)
        parts.append(f'<line x1="{x:.2f}" x2="{x:.2f}" y1="{y_high:.2f}" y2="{y_low:.2f}" stroke="{color}" stroke-width="{stroke_w}"/>')
        parts.append(
            f'<rect x="{x - candle_w / 2:.2f}" y="{body_y:.2f}" width="{candle_w:.2f}" height="{body_h:.2f}" '
            f'rx="1" fill="{color}" opacity="0.95"/>'
        )
        parts.append(
            f'<rect x="{x - candle_w / 2:.2f}" y="{vol_top:.2f}" width="{candle_w:.2f}" height="{vol_h:.2f}" '
            f'rx="1" fill="{color}" opacity="0.55"/>'
        )

    parts.append("</svg>")
    svg = "".join(parts)
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def score_signal(
    signal_code: str,
    channel_width: float,
    volume_mult: float,
    breakout_pct: float,
    max_gap_pct: float,
    cfg: ScanConfig,
) -> int:
    if signal_code == SIG_BASE:
        volume_score = min(70.0, volume_mult / max(cfg.base_volume_mult, 0.1) * 35.0)
        move_score = min(20.0, max(0.0, breakout_pct) * 2.0)
        return int(round(volume_score + move_score + 10.0))

    volume_floor = cfg.min_volume_mult
    max_width = cfg.max_channel_width_pct
    volume_score = min(45.0, volume_mult / max(volume_floor, 0.1) * 22.5)
    channel_score = max(
        0.0,
        min(25.0, (max_width - channel_width) / max(max_width, 0.1) * 25.0),
    )
    breakout_score = min(20.0, abs(breakout_pct) * 2.5)
    if signal_code == SIG_SURGE:
        breakout_score = min(breakout_score, 6.0)
    gap_score = max(0.0, min(10.0, (1 - max_gap_pct / max(cfg.max_gap_pct, 0.1)) * 10.0))
    return int(round(volume_score + channel_score + breakout_score + gap_score))


def score_vcp(setup: VcpSetup, cfg: ScanConfig) -> int:
    compression_pct = max(0.0, (setup.first_width_pct - setup.recent_width_pct) / max(setup.first_width_pct, 0.1) * 100)
    compression_score = min(35.0, compression_pct / max(cfg.vcp_min_compression_pct, 0.1) * 22.0)
    dry_score = max(0.0, min(25.0, (cfg.vcp_dry_volume_ratio - setup.dry_volume_ratio) / max(cfg.vcp_dry_volume_ratio, 0.1) * 35.0))
    near_high_score = max(0.0, min(25.0, (cfg.vcp_near_high_pct - setup.distance_to_high_pct) / max(cfg.vcp_near_high_pct, 0.1) * 25.0))
    tight_score = max(0.0, min(15.0, (cfg.vcp_max_recent_width_pct - setup.recent_width_pct) / max(cfg.vcp_max_recent_width_pct, 0.1) * 15.0))
    return int(round(compression_score + dry_score + near_high_score + tight_score))


def score_spring(setup: SpringSetup, cfg: ScanConfig) -> int:
    break_score = min(20.0, setup.break_pct / max(cfg.spring_break_pct, 0.1) * 10.0)
    reclaim_score = max(0.0, min(25.0, setup.reclaim_pct * 4.0 + 10.0))
    close_score = max(0.0, min(20.0, (setup.close_position_pct - cfg.spring_close_position_pct) / max(100.0 - cfg.spring_close_position_pct, 1.0) * 20.0))
    volume_score = min(25.0, setup.volume_mult / max(cfg.spring_volume_mult, 0.1) * 16.0)
    low_score = max(0.0, min(10.0, (cfg.spring_max_from_low_pct - setup.from_low_pct) / max(cfg.spring_max_from_low_pct, 0.1) * 10.0))
    return int(round(break_score + reclaim_score + close_score + volume_score + low_score))


def detect_signal(
    ticker_info: dict[str, Any],
    df: pd.DataFrame,
    cfg: ScanConfig,
    today: Any | None = None,
) -> dict[str, Any] | None:
    required_days = required_history_days(cfg)
    if df is None or len(df) < required_days + 2:
        return None

    df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
    if len(df) < required_days + 2:
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
    if cfg.scanner_mode != SCANNER_BASE and price * latest_volume < cfg.min_dollar_volume:
        return None

    if cfg.scanner_mode == SCANNER_BASE:
        base = build_base_impulse(df, cfg)
        if base is None:
            return None
        prev_close = float(df.iloc[-2]["Close"])
        latest_gap_pct = (latest_open - prev_close) / prev_close * 100 if prev_close > 0 else 0.0
        volume_over_max_pct = (base.volume_mult - 1) * 100
        score = score_signal(SIG_BASE, base.width_pct, base.volume_mult, base.move_pct, base.max_gap_pct, cfg)
        signal = SIGNAL_LABELS[SIG_BASE]
        return {
            "_sig": SIG_BASE,
            "_rvol": base.volume_mult,
            "_score": score,
            "_width": base.width_pct,
            "_gap": latest_gap_pct,
            "_move_pct": base.move_pct,
            "_volume_over_max_pct": volume_over_max_pct,
            "_chart_uri": pattern_chart_data_uri(
                df,
                cfg.base_impulse_days,
                base.low,
                base.high,
                "зона вчерашней свечи",
            ),
            "_scanner": cfg.scanner_mode,
            "Тикер": ticker_info["ticker"],
            "Название": (ticker_info.get("name") or "")[:34],
            "Биржа": ticker_info.get("exchange", ""),
            "Сигнал": signal,
            "Цена": round(price, 4),
            "Выход %": f"{base.move_pct:+.1f}%" if base.move_pct else "—",
            "Гэп сегодня": f"{latest_gap_pct:+.1f}%",
            "Объём ×": round(base.volume_mult, 2),
            "Объём": int(latest_volume),
            "Макс. объём периода": int(base.vol_max),
            "Ср. объём канала": int(base.vol_avg),
            "Ширина канала": f"{base.width_pct:.1f}%",
            "Канал": f"вчера ${base.low:.4f}-${base.high:.4f}",
            "Тело свечи %": round(base.body_pct, 1),
            "Долларовый объём": int(price * latest_volume),
            "Капитализация": ticker_info.get("market_cap") or 0,
            "Балл": score,
            "Источник": df.attrs.get("source", ""),
            "Время": now_et_str(),
        }

    prev_close = float(df.iloc[-2]["Close"])
    latest_gap_pct = (latest_open - prev_close) / prev_close * 100 if prev_close > 0 else 0.0
    body_pct = abs(price - latest_open) / latest_open * 100

    if cfg.scanner_mode == SCANNER_VCP:
        setup = build_vcp_setup(df, cfg)
        if setup is None:
            return None
        score = score_vcp(setup, cfg)
        return {
            "_sig": SIG_VCP,
            "_rvol": setup.current_volume_ratio,
            "_score": score,
            "_width": setup.base_width_pct,
            "_gap": latest_gap_pct,
            "_move_pct": setup.move_pct,
            "_chart_uri": pattern_chart_data_uri(
                df,
                cfg.vcp_days,
                setup.low,
                setup.high,
                "VCP-база",
            ),
            "_scanner": cfg.scanner_mode,
            "Тикер": ticker_info["ticker"],
            "Название": (ticker_info.get("name") or "")[:34],
            "Биржа": ticker_info.get("exchange", ""),
            "Сигнал": SIGNAL_LABELS[SIG_VCP],
            "Цена": round(price, 4),
            "Выход %": f"{setup.move_pct:+.1f}%",
            "Гэп сегодня": f"{latest_gap_pct:+.1f}%",
            "Объём ×": round(setup.current_volume_ratio, 2),
            "Объём": int(latest_volume),
            "Ср. объём канала": int(latest_volume / setup.current_volume_ratio) if setup.current_volume_ratio > 0 else 0,
            "Ширина канала": f"{setup.base_width_pct:.1f}%",
            "Канал": f"VCP ${setup.low:.4f}-${setup.high:.4f}",
            "Тело свечи %": round(body_pct, 1),
            "Сжатие": f"{setup.first_width_pct:.1f}% → {setup.recent_width_pct:.1f}%",
            "Сухой объём": f"{setup.dry_volume_ratio:.2f}×",
            "До верха": f"{setup.distance_to_high_pct:.1f}%",
            "Долларовый объём": int(price * latest_volume),
            "Капитализация": ticker_info.get("market_cap") or 0,
            "Балл": score,
            "Источник": df.attrs.get("source", ""),
            "Время": now_et_str(),
        }

    if cfg.scanner_mode == SCANNER_SPRING:
        setup = build_spring_setup(df, cfg)
        if setup is None:
            return None
        score = score_spring(setup, cfg)
        return {
            "_sig": SIG_SPRING,
            "_rvol": setup.volume_mult,
            "_score": score,
            "_width": setup.support_range_pct,
            "_gap": latest_gap_pct,
            "_move_pct": setup.move_pct,
            "_chart_uri": pattern_chart_data_uri(
                df,
                max(cfg.spring_support_days, 30),
                setup.support * 0.99,
                setup.support * 1.01,
                "поддержка Spring",
            ),
            "_scanner": cfg.scanner_mode,
            "Тикер": ticker_info["ticker"],
            "Название": (ticker_info.get("name") or "")[:34],
            "Биржа": ticker_info.get("exchange", ""),
            "Сигнал": SIGNAL_LABELS[SIG_SPRING],
            "Цена": round(price, 4),
            "Выход %": f"{setup.move_pct:+.1f}%",
            "Гэп сегодня": f"{latest_gap_pct:+.1f}%",
            "Объём ×": round(setup.volume_mult, 2),
            "Объём": int(latest_volume),
            "Ср. объём канала": int(latest_volume / setup.volume_mult) if setup.volume_mult > 0 else 0,
            "Ширина канала": f"{setup.support_range_pct:.1f}%",
            "Канал": f"поддержка ${setup.support:.4f} / прокол ${setup.latest_low:.4f}",
            "Тело свечи %": round(body_pct, 1),
            "Прокол": f"{setup.break_pct:.1f}%",
            "Возврат": f"{setup.reclaim_pct:+.1f}%",
            "Закрытие дня": f"{setup.close_position_pct:.0f}%",
            "Долларовый объём": int(price * latest_volume),
            "Капитализация": ticker_info.get("market_cap") or 0,
            "Балл": score,
            "Источник": df.attrs.get("source", ""),
            "Время": now_et_str(),
        }

    return None


def scan_market(
    ticker_infos: list[dict[str, Any]],
    cfg: ScanConfig,
    data_source: str,
    progress_box: Any,
    status_box: Any,
    table_box: Any,
    send_alerts: bool,
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    total = len(ticker_infos)
    st.session_state.stats = {"checked": 0, "signals": 0}
    st.session_state.scan_errors = []

    bars = load_bars(ticker_infos, cfg, data_source, progress_box, status_box)
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
            visible_hits = sort_results(hits, cfg.base_impulse_only)
            table_box.dataframe(
                display_frame(visible_hits, cfg.base_impulse_only),
                use_container_width=True,
                hide_index=True,
                column_config=display_column_config(cfg.base_impulse_only),
            )
            if send_alerts:
                notify_signal(row)

        st.session_state.stats["checked"] = idx

    return sort_results(hits, cfg.base_impulse_only)


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


def notification_key(row: dict[str, Any]) -> str:
    return f"{now_et().date().isoformat()}:{row.get('_scanner', '')}:{row['Тикер']}:{row.get('_sig') or row.get('Сигнал', '')}"


def notify_signal(row: dict[str, Any]) -> None:
    """Один Telegram-сигнал в день; помечаем только после успешной отправки."""
    notified = st.session_state.setdefault("notified_signals", set())
    key = notification_key(row)
    if key in notified:
        return
    if send_telegram(telegram_signal_message(row)):
        notified.add(key)


def telegram_signal_message(row: dict[str, Any]) -> str:
    ticker = html.escape(str(row["Тикер"]))
    rvol = safe_float(row.get("_rvol") or row.get("Объём ×"))
    if rvol <= 0:
        return f"{ticker} · RVOL — · —%"
    volume_pct = (rvol - 1.0) * 100
    return f"{ticker} · RVOL {rvol:.2f}x · {volume_pct:+.0f}%"


def result_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return str(row.get("_scanner", "")), str(row.get("Тикер", "")), str(row.get("Сигнал", ""))


def sort_results(rows: list[dict[str, Any]], base_pattern: bool = False) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            safe_float(row.get("Балл")),
            safe_float(row.get("_rvol")),
            abs(safe_float(row.get("_move_pct"))),
            safe_float(row.get("Объём")),
        ),
        reverse=True,
    )


def merge_results(new_rows: list[dict[str, Any]], old_rows: list[dict[str, Any]], base_pattern: bool = False) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in old_rows:
        merged[result_key(row)] = row
    for row in new_rows:
        merged[result_key(row)] = row
    return sort_results(list(merged.values()), base_pattern)


def result_matches_active_patterns(row: dict[str, Any], cfg: ScanConfig) -> bool:
    signal_code = str(row.get("_sig", ""))
    scanner = str(row.get("_scanner", ""))
    if scanner:
        return scanner == cfg.scanner_mode
    if cfg.scanner_mode == SCANNER_BASE:
        return signal_code == SIG_BASE
    if cfg.scanner_mode == SCANNER_VCP:
        return signal_code == SIG_VCP
    if cfg.scanner_mode == SCANNER_SPRING:
        return signal_code == SIG_SPRING
    return False


def filter_results_for_config(rows: list[dict[str, Any]], cfg: ScanConfig) -> list[dict[str, Any]]:
    return [row for row in rows if isinstance(row, dict) and result_matches_active_patterns(row, cfg)]


def format_price_cell(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value or "")
    decimals = 4 if number < 1 else 2
    return f"${number:,.{decimals}f}"


def format_volume_delta_cell(value: Any, volume_mult: Any) -> str:
    try:
        pct = float(value)
    except (TypeError, ValueError):
        pct = 0.0
    try:
        mult = float(volume_mult)
    except (TypeError, ValueError):
        mult = 0.0
    return f"+{pct:,.0f}%".replace(",", ".")


def format_rw_cell(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{number:,.1f}×".replace(",", ".")


def format_percent_cell(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{number:+,.1f}%".replace(",", ".")


def format_int_cell(value: Any) -> str:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return ""
    return f"{number:,}".replace(",", ".")


def format_dollar_cell(value: Any) -> str:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return ""
    if number <= 0:
        return ""
    return f"${number:,}".replace(",", ".")


def format_market_cap_cell(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if number <= 0:
        return "—"
    return f"${compact_number(number)}"


def format_signal_cell(row: pd.Series) -> str:
    sig = str(row.get("_sig", ""))
    if sig in SIGNAL_SHORT_LABELS:
        return SIGNAL_SHORT_LABELS[sig]
    raw = str(row.get("Сигнал", ""))
    replacements = {
        "ПРОБОЙ ВВЕРХ": "Пробой вверх",
        "ПРОБОЙ ВНИЗ": "Пробой вниз",
        "РАННИЙ ОБЪЁМ В КАНАЛЕ": "Ранний объём",
        "ВЗРЫВ ОБЪЁМА ИЗ БАЗЫ": "Взрыв базы",
    }
    return replacements.get(raw, raw)


def display_column_config(base_pattern: bool = False) -> dict[str, Any]:
    return {
        "Тикер": st.column_config.TextColumn("Тикер", width="small"),
        "Сигнал": st.column_config.TextColumn("Сигнал", width="medium"),
        "Цена": st.column_config.TextColumn("Цена", width="small"),
        "RVOL": st.column_config.TextColumn(
            "RVOL",
            width="small",
            help="Сегодняшний объём / выбранная база сравнения объёма. Для взрыва базы это максимум любой из предыдущих свечей.",
        ),
        "Движение %": st.column_config.TextColumn("Движение %", width="small"),
        "Объём": st.column_config.TextColumn("Объём", width="medium"),
        "Долларовый объём": st.column_config.TextColumn("Долларовый объём", width="medium"),
        "Капитализация": st.column_config.TextColumn("Капитализация", width="medium"),
        "Время": st.column_config.TextColumn("Время", width="small"),
    }


def display_frame(rows: list[dict[str, Any]], base_pattern: bool = False, include_chart: bool = True) -> pd.DataFrame:
    display_cols = DISPLAY_COLS
    if not rows:
        columns = display_cols if include_chart else [col for col in display_cols if col != "График"]
        return pd.DataFrame(columns=columns)

    frame = pd.DataFrame(rows)
    if "Сигнал" in frame.columns:
        frame["Сигнал"] = frame.apply(format_signal_cell, axis=1)
    if "Цена" in frame.columns:
        frame["Цена"] = frame["Цена"].map(format_price_cell)
    if "_rvol" in frame.columns:
        frame["RVOL"] = frame["_rvol"].map(format_rw_cell)
    elif "Объём ×" in frame.columns:
        frame["RVOL"] = frame["Объём ×"].map(format_rw_cell)
    if "_move_pct" in frame.columns:
        frame["Движение %"] = frame["_move_pct"].map(format_percent_cell)
    elif "Выход %" in frame.columns:
        frame["Движение %"] = frame["Выход %"].map(format_percent_cell)
    if "Объём" in frame.columns:
        frame["Объём"] = frame["Объём"].map(format_int_cell)
    if "Долларовый объём" in frame.columns:
        frame["Долларовый объём"] = frame["Долларовый объём"].map(format_dollar_cell)
    if "Капитализация" in frame.columns:
        frame["Капитализация"] = frame["Капитализация"].map(format_market_cap_cell)
    if not include_chart and "График" in display_cols:
        display_cols = [col for col in display_cols if col != "График"]

    columns = [col for col in display_cols if col in frame.columns]
    return frame[columns]


def render_results_summary(rows: list[dict[str, Any]]) -> None:
    count = len(rows)
    best_rvol = max((safe_float(row.get("_rvol")) for row in rows), default=0.0)
    total_dollar_volume = sum(safe_float(row.get("Долларовый объём")) for row in rows)
    latest_time = str(rows[0].get("Время", now_et_str())) if rows else now_et_str()
    count_parts = []
    for code in (SIG_BASE, SIG_VCP, SIG_SPRING, SIG_UP, SIG_DOWN, SIG_SURGE):
        signal_count = sum(1 for row in rows if str(row.get("_sig", "")) == code)
        if signal_count:
            count_parts.append(f"{SIGNAL_SHORT_LABELS.get(code, code)} {signal_count}")
    signal_mix = " · ".join(count_parts) if count_parts else "нет"
    st.markdown(
        f"""
        <div class="base-results-bar">
            <div>
                <div class="base-results-title">Найденные акции</div>
                <div class="base-results-subtitle">Сортировка по сегодняшнему объёму, затем по RVOL и движению.</div>
            </div>
            <div class="base-results-stats">
                {chip("Найдено", count, "blue")}
                {chip("Лучший RVOL", format_rw_cell(best_rvol), "green")}
                {chip("Долларовый объём", format_market_cap_cell(total_dollar_volume), "amber")}
                {chip("Состав", signal_mix)}
                {chip("Обновлено", latest_time)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_chart_option(row: dict[str, Any]) -> str:
    return (
        f"{row.get('Тикер', '')} · {row.get('Сигнал', '')} · "
        f"балл {row.get('Балл', '')} · выход {row.get('Выход %', '—')} · объём ×{row.get('Объём ×', '—')}"
    )


def build_signal_chart(df: pd.DataFrame, cfg: ScanConfig, signal_code: str | None = None) -> alt.Chart | None:
    base = build_base_impulse(df, cfg) if signal_code == SIG_BASE else None
    vcp = build_vcp_setup(df, cfg) if signal_code == SIG_VCP else None
    spring = build_spring_setup(df, cfg) if signal_code == SIG_SPRING else None
    if base is not None:
        line_low = base.low
        line_high = base.high
        line_volume_avg = base.vol_avg
        lookback_days = cfg.base_impulse_days
        high_label = "Верх вчерашней свечи"
        low_label = "Низ вчерашней свечи"
        volume_label = "Средний объём 10 свечей"
    elif vcp is not None:
        line_low = vcp.low
        line_high = vcp.high
        line_volume_avg = float(pd.to_numeric(df.tail(cfg.vcp_days)["Volume"], errors="coerce").dropna().mean())
        lookback_days = cfg.vcp_days
        high_label = "Верх VCP-базы"
        low_label = "Низ VCP-базы"
        volume_label = "Средний объём VCP"
    elif spring is not None:
        line_low = spring.support * 0.99
        line_high = spring.support * 1.01
        line_volume_avg = float(pd.to_numeric(df.iloc[-(cfg.spring_support_days + 1) : -1]["Volume"], errors="coerce").dropna().mean())
        lookback_days = max(30, cfg.spring_support_days)
        high_label = "Зона поддержки +1%"
        low_label = "Зона поддержки -1%"
        volume_label = "Средний объём поддержки"
    else:
        return None

    chart_df = df.tail(lookback_days + 8).reset_index()
    chart_df.rename(columns={chart_df.columns[0]: "Date"}, inplace=True)
    chart_df["Date"] = pd.to_datetime(chart_df["Date"], errors="coerce")
    if getattr(chart_df["Date"].dt, "tz", None) is not None:
        chart_df["Date"] = chart_df["Date"].dt.tz_convert(None)
    chart_df = chart_df.dropna(subset=["Date", "Open", "High", "Low", "Close", "Volume"]).copy()
    if chart_df.empty:
        return None

    chart_df["Направление"] = chart_df.apply(lambda row: "Вверх" if row["Close"] >= row["Open"] else "Вниз", axis=1)
    channel_df = pd.DataFrame(
        {
            "Уровень": [line_high, line_low],
            "Линия": [high_label, low_label],
        }
    )
    volume_df = pd.DataFrame({"Уровень": [line_volume_avg], "Линия": [volume_label]})
    latest_df = chart_df.tail(1).copy()

    price_scale_min = min(float(chart_df["Low"].min()), line_low) * 0.985
    price_scale_max = max(float(chart_df["High"].max()), line_high) * 1.015

    color_scale = alt.Scale(domain=["Вверх", "Вниз"], range=["#047857", "#b42318"])
    wick = (
        alt.Chart(chart_df)
        .mark_rule()
        .encode(
            x=alt.X("Date:T", title=None),
            y=alt.Y("Low:Q", title="Цена", scale=alt.Scale(domain=[price_scale_min, price_scale_max])),
            y2="High:Q",
            color=alt.Color("Направление:N", scale=color_scale, legend=None),
            tooltip=[
                alt.Tooltip("Date:T", title="Дата"),
                alt.Tooltip("Open:Q", title="Open", format=".4f"),
                alt.Tooltip("High:Q", title="High", format=".4f"),
                alt.Tooltip("Low:Q", title="Low", format=".4f"),
                alt.Tooltip("Close:Q", title="Close", format=".4f"),
                alt.Tooltip("Volume:Q", title="Volume", format=",.0f"),
            ],
        )
    )
    body = (
        alt.Chart(chart_df)
        .mark_bar(size=9)
        .encode(
            x=alt.X("Date:T", title=None),
            y=alt.Y("Open:Q", title="Цена", scale=alt.Scale(domain=[price_scale_min, price_scale_max])),
            y2="Close:Q",
            color=alt.Color("Направление:N", scale=color_scale, legend=None),
        )
    )
    channel_lines = (
        alt.Chart(channel_df)
        .mark_rule(strokeDash=[6, 4], size=2)
        .encode(
            y=alt.Y("Уровень:Q", title="Цена", scale=alt.Scale(domain=[price_scale_min, price_scale_max])),
            color=alt.Color("Линия:N", scale=alt.Scale(range=["#175cd3", "#b54708"]), legend=alt.Legend(orient="top")),
        )
    )
    open_marker = (
        alt.Chart(latest_df)
        .mark_point(filled=True, shape="diamond", size=95, color="#175cd3")
        .encode(
            x=alt.X("Date:T", title=None),
            y=alt.Y("Open:Q", title="Цена", scale=alt.Scale(domain=[price_scale_min, price_scale_max])),
            tooltip=[
                alt.Tooltip("Date:T", title="Дата"),
                alt.Tooltip("Open:Q", title="Открытие", format=".4f"),
                alt.Tooltip("Close:Q", title="Закрытие", format=".4f"),
            ],
        )
    )
    price_chart = alt.layer(wick, body, channel_lines, open_marker).properties(height=330)

    volume_bars = (
        alt.Chart(chart_df)
        .mark_bar(size=9, opacity=0.72)
        .encode(
            x=alt.X("Date:T", title=None),
            y=alt.Y("Volume:Q", title="Объём"),
            color=alt.Color("Направление:N", scale=color_scale, legend=None),
            tooltip=[
                alt.Tooltip("Date:T", title="Дата"),
                alt.Tooltip("Volume:Q", title="Volume", format=",.0f"),
            ],
        )
    )
    volume_avg = (
        alt.Chart(volume_df)
        .mark_rule(strokeDash=[5, 4], color="#667085")
        .encode(y=alt.Y("Уровень:Q", title="Объём"))
    )
    volume_chart = alt.layer(volume_bars, volume_avg).properties(height=105)

    return alt.vconcat(price_chart, volume_chart).resolve_scale(x="shared")


def render_signal_gallery(rows: list[dict[str, Any]]) -> None:
    cards = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("_chart_uri")
    ]
    if not cards:
        return

    st.markdown('<div class="desk-section-title">Графики найденных акций</div>', unsafe_allow_html=True)
    max_cards = min(len(cards), 60)
    columns = st.columns(2, gap="large")
    for idx, row in enumerate(cards[:max_cards]):
        chart_uri = str(row.get("_chart_uri", ""))
        if not chart_uri:
            continue
        ticker = html.escape(str(row.get("Тикер", "")))
        signal = html.escape(SIGNAL_SHORT_LABELS.get(str(row.get("_sig", "")), str(row.get("Сигнал", ""))))
        price = html.escape(format_price_cell(row.get("Цена")))
        rw = html.escape(format_rw_cell(row.get("_rvol")))
        move = html.escape(format_percent_cell(row.get("_move_pct")))
        volume = html.escape(format_int_cell(row.get("Объём")))
        dollar_volume = html.escape(format_dollar_cell(row.get("Долларовый объём")))
        market_cap = html.escape(format_market_cap_cell(row.get("Капитализация")))
        with columns[idx % 2]:
            st.markdown(
                f"""
                <div class="pattern-chart-card">
                    <div class="pattern-chart-head">
                        <div>
                            <div class="pattern-chart-symbol">{ticker}</div>
                            <div class="desk-muted">{signal}</div>
                        </div>
                        <div class="pattern-chart-meta">{price}<br>{rw} · {move}</div>
                    </div>
                    <div class="pattern-chart-stats">
                        <div class="pattern-chart-stat"><span>Объём</span><strong>{volume}</strong></div>
                        <div class="pattern-chart-stat"><span>$ объём</span><strong>{dollar_volume}</strong></div>
                        <div class="pattern-chart-stat"><span>Капитал</span><strong>{market_cap}</strong></div>
                        <div class="pattern-chart-stat"><span>Время</span><strong>{html.escape(str(row.get("Время", "")))}</strong></div>
                    </div>
                    <img src="{html.escape(chart_uri, quote=True)}" alt="{ticker} chart" />
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_signal_chart(rows: list[dict[str, Any]], cfg: ScanConfig, data_source: str) -> None:
    clean_rows = [row for row in rows if isinstance(row, dict) and row.get("Тикер")]
    if not clean_rows:
        return

    st.markdown('<div class="desk-section-title">График сигнала</div>', unsafe_allow_html=True)
    selected_idx = st.selectbox(
        "Сигнал на графике",
        list(range(len(clean_rows))),
        format_func=lambda idx: format_chart_option(clean_rows[idx]),
        key="signal_chart_selector",
    )
    selected = clean_rows[int(selected_idx)]
    ticker = str(selected.get("Тикер", "")).upper()
    history_days = required_history_days(cfg)
    history = fetch_daily_history(ticker, history_days, data_source)
    if history is None:
        st.warning(f"Не удалось загрузить график для {ticker} через {DATA_SOURCE_LABELS.get(data_source, data_source)}.")
        return

    chart = build_signal_chart(history, cfg, str(selected.get("_sig", "")))
    if chart is None:
        st.warning(f"Недостаточно свечей для графика {ticker}.")
        return

    if str(selected.get("_sig", "")) == SIG_BASE or cfg.base_impulse_only:
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Тикер", ticker)
        m2.metric("Сигнал", "Взрыв базы")
        m3.metric("Цена", format_price_cell(selected.get("Цена")))
        m4.metric("RVOL", format_rw_cell(selected.get("_rvol")))
        m5.metric("Движение", format_percent_cell(selected.get("_move_pct")))
        m6.metric("Объём", format_int_cell(selected.get("Объём")))
    else:
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Тикер", ticker)
        m2.metric("Сигнал", str(selected.get("Сигнал", "")))
        m3.metric("Канал", str(selected.get("Канал", "—")))
        m4.metric("Объём ×", str(selected.get("Объём ×", "—")))
        m5.metric("Гэп сегодня", str(selected.get("Гэп сегодня", "—")))
    st.altair_chart(chart, use_container_width=True)


# ── FORMAT HELPERS ──────────────────────────────────────────────────
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
if "auto_scan_offset" not in st.session_state:
    st.session_state.auto_scan_offset = 0
if "auto_scan_signature" not in st.session_state:
    st.session_state.auto_scan_signature = ""
if "last_auto_total" not in st.session_state:
    st.session_state.last_auto_total = None


# ── SIDEBAR ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand-title">PR Screener</div>
            <div class="sidebar-brand-subtitle">Взрыв базы · VCP · Spring</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="desk-section-title">Тип скринера</div>', unsafe_allow_html=True)
    scanner_names = list(SCANNER_LABELS.values())
    scanner_label = st.radio(
        "Активный скринер",
        scanner_names,
        index=0,
        horizontal=False,
        help=(
            "Выбери один активный поиск. Настройки остальных режимов ниже останутся видны, "
            "но будут серыми и не будут участвовать в скане."
        ),
    )
    scanner_mode = {label: code for code, label in SCANNER_LABELS.items()}[scanner_label]
    base_impulse_only = scanner_mode == SCANNER_BASE
    vcp_active = scanner_mode == SCANNER_VCP
    spring_active = scanner_mode == SCANNER_SPRING
    st.caption(SCANNER_HELP[scanner_mode])

    st.markdown('<div class="desk-section-title">Данные</div>', unsafe_allow_html=True)
    data_source_label = st.selectbox(
        "Свечи, канал и дневной объём",
        [
            DATA_SOURCE_LABELS[DATA_SOURCE_AUTO],
            DATA_SOURCE_LABELS[DATA_SOURCE_ALPACA_SIP],
            DATA_SOURCE_LABELS[DATA_SOURCE_YAHOO],
        ],
        index=0,
        help=(
            "Alpaca SIP delayed — полный рынок SIP/CTA/UTP по всем биржам с задержкой 16 минут. "
            "Yahoo остаётся резервом, если Alpaca не отдаст тикер."
        ),
    )
    data_source = {label: code for code, label in DATA_SOURCE_LABELS.items()}[data_source_label]
    if data_source in {DATA_SOURCE_AUTO, DATA_SOURCE_ALPACA_SIP}:
        st.caption(f"Alpaca SIP delayed: полный рынок, задержка {ALPACA_SIP_DELAY_MINUTES} минут.")
        if not (ALPACA_KEY and ALPACA_SECRET):
            st.warning("Для Alpaca SIP delayed нужны ALPACA_KEY и ALPACA_SECRET в secrets.")
    if data_source in {DATA_SOURCE_AUTO, DATA_SOURCE_YAHOO} and yf is None:
        st.warning("yfinance не установлен: Yahoo Finance недоступен как резерв.")

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
    max_tickers = st.slider(
        "Акций за прогон",
        50,
        10000,
        5000,
        50,
        help=(
            "Ручной запуск проверит только эту пачку и остановится. "
            f"Авто-скан будет идти по всему списку до {AUTO_SCAN_MARKET_LIMIT:,} акций такими пачками."
        ),
    )
    st.caption("NASDAQ/NYSE/AMEX · обычные акции до 5 букв · без ETF, фондов, юнитов, варрантов, прав, привилегированных акций и долговых нот")

    channel_days = 14
    max_channel_width_pct = 8.0
    price_basis = "HIGH_LOW"
    max_gap_pct = 8.0
    breakout_buffer_pct = 0.0
    directions = "ALL"
    require_price_break = False
    allow_volume_alert_inside_channel = False
    volume_baseline = "MAX"
    min_volume_mult = 1.0
    min_channel_avg_volume = 0

    st.markdown('<div class="desk-section-title">Свежесть и ликвидность</div>', unsafe_allow_html=True)
    max_stale_days = st.slider(
        "Свежесть последней свечи, дней",
        1,
        10,
        5,
        help="Отбрасывает тикеры, у которых последний дневной бар слишком старый.",
    )
    min_dollar_volume_input = st.number_input(
        "Мин. долларовый объём сегодня",
        0,
        100_000_000,
        250_000,
        50_000,
        disabled=base_impulse_only,
        help="Для VCP и Spring фильтрует слишком тонкие акции. Для Взрыва из базы выключено, чтобы старый режим работал как раньше.",
    )
    min_dollar_volume = 0 if base_impulse_only else int(min_dollar_volume_input)

    st.markdown('<div class="desk-section-title">Взрыв из базы</div>', unsafe_allow_html=True)
    base_impulse_enabled = base_impulse_only
    base_impulse_days = st.slider(
        "Предыдущих свечей для сравнения объёма",
        5,
        20,
        10,
        1,
        disabled=not base_impulse_only,
        help=SCANNER_HELP[SCANNER_BASE],
    )
    base_volume_mult = st.slider(
        "Сегодняшний объём выше каждой прошлой свечи ×",
        1,
        50,
        10,
        1,
        disabled=not base_impulse_only,
        help="1 означает: сегодняшний объём строго больше максимального объёма среди предыдущих свечей. 50 означает: больше максимума предыдущих свечей в 50 раз.",
    )

    st.markdown('<div class="desk-section-title">VCP-сжатие</div>', unsafe_allow_html=True)
    vcp_days = st.slider(
        "Период VCP, дней",
        30,
        90,
        45,
        5,
        disabled=not vcp_active,
        help=SCANNER_HELP[SCANNER_VCP],
    )
    vcp_max_base_width_pct = st.slider("Макс. ширина всей базы (%)", 15.0, 70.0, 35.0, 1.0, disabled=not vcp_active)
    vcp_max_recent_width_pct = st.slider("Макс. ширина последней трети (%)", 3.0, 25.0, 12.0, 0.5, disabled=not vcp_active)
    vcp_min_compression_pct = st.slider("Минимальное сжатие диапазона (%)", 10.0, 70.0, 25.0, 1.0, disabled=not vcp_active)
    vcp_near_high_pct = st.slider("Цена не дальше от верха базы (%)", 2.0, 20.0, 8.0, 0.5, disabled=not vcp_active)
    vcp_dry_volume_ratio = st.slider(
        "Сухой объём: последняя треть / первые две",
        0.30,
        1.20,
        0.85,
        0.05,
        disabled=not vcp_active,
        help="0.85 значит: средний объём последней трети базы должен быть не выше 85% от среднего объёма первых двух третей.",
    )

    st.markdown('<div class="desk-section-title">Spring-отскок</div>', unsafe_allow_html=True)
    spring_support_days = st.slider("Поддержка за дней", 30, 120, 60, 5, disabled=not spring_active, help=SCANNER_HELP[SCANNER_SPRING])
    spring_low_days = st.slider("Дно смотреть за дней", 60, 250, 120, 10, disabled=not spring_active)
    spring_break_pct = st.slider("Минимальный прокол поддержки (%)", 0.1, 10.0, 1.0, 0.1, disabled=not spring_active)
    spring_reclaim_pct = st.slider("Возврат выше поддержки (%)", 0.0, 5.0, 0.0, 0.1, disabled=not spring_active)
    spring_close_position_pct = st.slider(
        "Закрытие в верхней части свечи (%)",
        40.0,
        90.0,
        60.0,
        1.0,
        disabled=not spring_active,
        help="60% значит: закрытие должно быть выше середины дневного диапазона и ближе к high.",
    )
    spring_volume_mult = st.slider("Объём выше среднего ×", 1.0, 5.0, 1.2, 0.1, disabled=not spring_active)
    spring_max_from_low_pct = st.slider("Цена не дальше от дна периода (%)", 5.0, 80.0, 35.0, 1.0, disabled=not spring_active)

    st.markdown('<div class="desk-section-title">Цена</div>', unsafe_allow_html=True)
    price_col_1, price_col_2 = st.columns(2)
    with price_col_1:
        min_price = st.number_input(
            "Мин. цена",
            0.01,
            500.0,
            0.10 if base_impulse_only else 0.50,
            0.01 if base_impulse_only else 0.10,
        )
    with price_col_2:
        max_price = st.number_input("Макс. цена", 0.01, 500.0, 20.0, 1.0)

    st.markdown('<div class="desk-section-title">Автоматизация</div>', unsafe_allow_html=True)
    send_alerts = st.toggle("Telegram-уведомления", value=True)
    telegram_configured = bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)
    if st.button("Отправить тест Telegram", use_container_width=True, disabled=not telegram_configured):
        if send_telegram("TEST · RVOL 1.00x · +0%"):
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
    scanner_mode=scanner_mode,
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
    base_impulse_enabled=base_impulse_enabled,
    base_impulse_days=base_impulse_days,
    base_volume_mult=base_volume_mult,
    base_impulse_only=base_impulse_only,
    max_gap_pct=max_gap_pct,
    max_stale_days=max_stale_days,
    min_price=min_price,
    max_price=max_price,
    vcp_days=vcp_days,
    vcp_max_base_width_pct=vcp_max_base_width_pct,
    vcp_max_recent_width_pct=vcp_max_recent_width_pct,
    vcp_min_compression_pct=vcp_min_compression_pct,
    vcp_near_high_pct=vcp_near_high_pct,
    vcp_dry_volume_ratio=vcp_dry_volume_ratio,
    spring_support_days=spring_support_days,
    spring_low_days=spring_low_days,
    spring_break_pct=spring_break_pct,
    spring_reclaim_pct=spring_reclaim_pct,
    spring_close_position_pct=spring_close_position_pct,
    spring_volume_mult=spring_volume_mult,
    spring_max_from_low_pct=spring_max_from_low_pct,
)

telegram_ready = bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)
telegram_tone = "green" if send_alerts and telegram_ready else ("red" if send_alerts else "amber")
telegram_label = "готов" if send_alerts and telegram_ready else ("нет секрета" if send_alerts else "выкл")
mode_subtitle = SCANNER_SUBTITLES.get(cfg.scanner_mode, "")
mode_label = SCANNER_LABELS.get(cfg.scanner_mode, "Скринер")

st.markdown(
    f"""
    <div class="desk-header">
        <div>
            <div class="desk-title">PR Screener</div>
            <div class="desk-subtitle">{html.escape(mode_subtitle)}</div>
        </div>
        <div class="desk-statusbar">
            {chip("Рынок", status_text, status_tone)}
            {chip("Время ET", now_et_str("%H:%M"), "blue")}
            {chip("Телеграм", telegram_label, telegram_tone)}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if cfg.scanner_mode == SCANNER_BASE:
    setup_chips = "".join(
        [
            chip("Режим", mode_label, "amber"),
            chip("Биржа", exchange),
            chip("За прогон", max_tickers),
            chip("Цена", f"${min_price:g}-${max_price:g}"),
            chip("Открытие", "внутри вчерашней свечи", "blue"),
            chip("RVOL", f">{cfg.base_volume_mult:g}x к макс. из {cfg.base_impulse_days}"),
            chip("Свежесть", f"{cfg.max_stale_days}д"),
            chip("Источник", DATA_SOURCE_LABELS.get(data_source, data_source), "green"),
        ]
    )
elif cfg.scanner_mode == SCANNER_VCP:
    setup_chips = "".join(
        [
            chip("Режим", mode_label, "blue"),
            chip("Биржа", exchange),
            chip("За прогон", max_tickers),
            chip("Цена", f"${min_price:g}-${max_price:g}"),
            chip("VCP", f"{cfg.vcp_days} дней"),
            chip("База", f"до {cfg.vcp_max_base_width_pct:g}%"),
            chip("Последняя треть", f"до {cfg.vcp_max_recent_width_pct:g}%"),
            chip("Сжатие", f"от {cfg.vcp_min_compression_pct:g}%"),
            chip("До верха", f"до {cfg.vcp_near_high_pct:g}%"),
            chip("Сухой объём", f"≤ {cfg.vcp_dry_volume_ratio:g}x"),
            chip("Свежесть", f"{cfg.max_stale_days}д"),
            chip("Свечи/объём", DATA_SOURCE_LABELS.get(data_source, data_source), "green"),
            chip("Долларовый объём", f"${cfg.min_dollar_volume:,}"),
        ]
    )
else:
    setup_chips = "".join(
        [
            chip("Режим", mode_label, "green"),
            chip("Биржа", exchange),
            chip("За прогон", max_tickers),
            chip("Цена", f"${min_price:g}-${max_price:g}"),
            chip("Поддержка", f"{cfg.spring_support_days} дней"),
            chip("Дно", f"{cfg.spring_low_days} дней"),
            chip("Прокол", f"от {cfg.spring_break_pct:g}%"),
            chip("Возврат", f"{cfg.spring_reclaim_pct:g}%"),
            chip("Закрытие", f"верх {cfg.spring_close_position_pct:g}%"),
            chip("Объём", f"×{cfg.spring_volume_mult:g}"),
            chip("От дна", f"до {cfg.spring_max_from_low_pct:g}%"),
            chip("Свечи/объём", DATA_SOURCE_LABELS.get(data_source, data_source), "green"),
            chip("Долларовый объём", f"${cfg.min_dollar_volume:,}"),
        ]
    )
st.markdown(
    f"""
    <div class="desk-filter-board">
        <div class="desk-filter-title">Параметры скана</div>
        <div class="desk-chipbar">{setup_chips}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if data_source in {DATA_SOURCE_AUTO, DATA_SOURCE_YAHOO} and yf is None:
    st.warning("yfinance не установлен. Установи пакет: pip install yfinance")
if send_alerts and not telegram_ready:
    st.warning(
        "Telegram включён, но TELEGRAM_TOKEN или TELEGRAM_CHAT_ID не найдены в Streamlit secrets. "
        "В таком режиме уведомления в бот отправляться не будут."
    )

batch_size = int(max_tickers)
if auto_scan:
    current = now_et()
    if st.session_state.auto_last_run:
        elapsed_sec = int((current - st.session_state.auto_last_run).total_seconds())
        remaining = max(0, auto_interval * 60 - elapsed_sec)
        should_auto_run = elapsed_sec >= auto_interval * 60
        last_auto_total = int(st.session_state.last_auto_total or 0)
        next_range_hint = ""
        if last_auto_total > 0:
            next_start = min(int(st.session_state.auto_scan_offset or 0), max(0, last_auto_total - 1))
            next_end = min(next_start + batch_size, last_auto_total)
            next_range_hint = f" · следующая пачка: {next_start + 1}-{next_end} из {last_auto_total}"
        auto_text = (
            f"Авто-скан: каждые {auto_interval} мин · последний {elapsed_sec // 60} мин назад · "
            f"следующий через {remaining // 60} мин · пачка {batch_size} акций · "
            f"рынок до {AUTO_SCAN_MARKET_LIMIT:,}{next_range_hint}"
        )
    else:
        should_auto_run = True
        auto_text = (
            f"Авто-скан: каждые {auto_interval} мин · первый запуск ожидается · "
            f"пачка {batch_size} акций · рынок до {AUTO_SCAN_MARKET_LIMIT:,}"
        )
else:
    should_auto_run = False
    auto_text = f"Ручной запуск: проверит первые {batch_size} акций и остановится."

st.markdown(f'<div class="desk-muted" style="margin:-0.2rem 0 0.65rem;">{html.escape(auto_text)}</div>', unsafe_allow_html=True)

button_col, clear_col = st.columns([1, 1])
with button_col:
    start_scan = st.button("Сканировать рынок", type="primary", use_container_width=True)
with clear_col:
    if st.button("Очистить результаты", use_container_width=True):
        st.session_state.results = []
        st.session_state.stats = {"checked": 0, "signals": 0}
        st.session_state.auto_scan_offset = 0
        st.session_state.auto_scan_signature = ""
        st.session_state.last_auto_total = None
        st.rerun()


if start_scan or (auto_scan and should_auto_run):
    is_auto_batch = bool(auto_scan and should_auto_run and not start_scan)
    all_tickers_full = get_nasdaq_tickers(exchange, max_scan_price)
    batch_size = max(1, int(max_tickers))

    if is_auto_batch:
        all_tickers = all_tickers_full[:AUTO_SCAN_MARKET_LIMIT]
        auto_signature = f"{exchange}:{max_scan_price:g}:{AUTO_SCAN_MARKET_LIMIT}:{len(all_tickers)}"
        if st.session_state.auto_scan_signature != auto_signature:
            st.session_state.auto_scan_signature = auto_signature
            st.session_state.auto_scan_offset = 0

        scan_start = int(st.session_state.auto_scan_offset or 0)
        if scan_start >= len(all_tickers):
            scan_start = 0
        scan_end = min(scan_start + batch_size, len(all_tickers))
        ticker_infos = all_tickers[scan_start:scan_end]
        scan_scope = f"авто {scan_start + 1}-{scan_end} из {len(all_tickers)}"
        st.session_state.last_auto_total = len(all_tickers)
    else:
        all_tickers = all_tickers_full
        scan_start = 0
        scan_end = min(batch_size, len(all_tickers))
        ticker_infos = all_tickers[:scan_end]
        scan_scope = f"ручной первые {len(ticker_infos)} из {len(all_tickers)}"

    if not ticker_infos:
        st.error("Нет тикеров для сканирования.")
    else:
        progress_box = st.progress(0.0)
        status_box = st.empty()
        table_box = st.empty()

        hits = scan_market(
            ticker_infos=ticker_infos,
            cfg=cfg,
            data_source=data_source,
            progress_box=progress_box,
            status_box=status_box,
            table_box=table_box,
            send_alerts=send_alerts,
        )

        active_old_results = filter_results_for_config(st.session_state.results, cfg)
        st.session_state.results = merge_results(hits, active_old_results, cfg.base_impulse_only)

        st.session_state.auto_last_run = now_et()
        st.session_state.auto_count += 1
        progress_box.progress(1.0)
        progress_box.empty()
        table_box.empty()
        status_box.empty()

        if is_auto_batch:
            next_offset = scan_end
            if next_offset >= len(all_tickers):
                next_offset = 0
            st.session_state.auto_scan_offset = next_offset

        if hits:
            done_message = (
                f"Готово: найдено {len(hits)} сигналов · "
                f"проверено {len(ticker_infos)} · {scan_scope}"
            )
            status_box.success(done_message)
            if hasattr(st, "toast"):
                st.toast(done_message, icon="✅")
        else:
            done_message = f"Скан завершён: сигналов нет · проверено {len(ticker_infos)} · {scan_scope}"
            status_box.info(done_message)
            if hasattr(st, "toast") and not is_auto_batch:
                st.toast(done_message, icon="ℹ️")

        if st.session_state.scan_errors:
            with st.expander("Диагностика"):
                st.write("\n".join(st.session_state.scan_errors))

st.session_state.results = sort_results(filter_results_for_config(st.session_state.results, cfg), cfg.base_impulse_only)

if st.session_state.results:
    df_results = pd.DataFrame(st.session_state.results)
    if "_sig" in df_results.columns:
        up_mask = df_results["_sig"].eq(SIG_UP)
        down_mask = df_results["_sig"].eq(SIG_DOWN)
        early_mask = df_results["_sig"].eq(SIG_SURGE)
        base_mask = df_results["_sig"].eq(SIG_BASE)
    else:
        up_mask = df_results["Сигнал"].isin(["ПРОБОЙ ВВЕРХ", "BREAKOUT UP"])
        down_mask = df_results["Сигнал"].isin(["ПРОБОЙ ВНИЗ", "BREAKDOWN DOWN"])
        early_mask = df_results["Сигнал"].isin(["РАННИЙ ОБЪЁМ В КАНАЛЕ", "VOLUME IN CHANNEL"])
        base_mask = df_results["Сигнал"].isin(["ВЗРЫВ ОБЪЁМА ИЗ БАЗЫ"])
    up_count = int(up_mask.sum())
    down_count = int(down_mask.sum())
    early_count = int(early_mask.sum())
    base_count = int(base_mask.sum())
    best_score = int(df_results["Балл"].max()) if "Балл" in df_results else 0

    render_results_summary(st.session_state.results)
    st.dataframe(
        display_frame(st.session_state.results, cfg.base_impulse_only),
        use_container_width=True,
        hide_index=True,
        column_config=display_column_config(cfg.base_impulse_only),
        height=420,
    )
    render_signal_gallery(st.session_state.results)

    csv = display_frame(st.session_state.results, cfg.base_impulse_only, include_chart=False).to_csv(index=False).encode("utf-8")
    st.download_button(
        "Скачать CSV",
        data=csv,
        file_name=f"accumulation_breakout_{now_et().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )
else:
    empty_title = "Найденных акций пока нет"
    empty_text = "Ожидание совпадений по текущим рыночным фильтрам."
    st.markdown(
        f"""
        <div class="desk-empty-panel">
            <div>
                <div class="desk-empty-title">{empty_title}</div>
                <div class="desk-muted">{empty_text}</div>
            </div>
            <div class="base-results-stats">
                {chip("Режим", mode_label, "blue" if not cfg.base_impulse_only else "amber")}
                {chip("Источник", DATA_SOURCE_LABELS.get(data_source, data_source), "green")}
                {chip("Время ET", now_et_str("%H:%M"))}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
