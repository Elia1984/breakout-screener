from __future__ import annotations

import html
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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

AUTOREFRESH_IMPORT_ERROR = ""
try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None
except Exception as exc:
    st_autorefresh = None
    AUTOREFRESH_IMPORT_ERROR = str(exc)


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

            #MainMenu,
            footer {
                display: none !important;
                visibility: hidden;
                height: 0 !important;
                min-height: 0 !important;
            }

            header[data-testid="stHeader"] {
                display: block !important;
                visibility: visible !important;
                background: rgba(238, 242, 246, 0.96);
                box-shadow: none;
            }

            div[data-testid="stAppDeployButton"],
            span[data-testid="stMainMenu"] {
                display: none !important;
                visibility: hidden !important;
                width: 0 !important;
                min-width: 0 !important;
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

            .ai-analysis-panel {
                background: #ffffff;
                border: 1.5px solid var(--desk-blue);
                border-radius: 8px;
                padding: 0.85rem 0.95rem;
                margin: 0.85rem 0;
                box-shadow: 0 10px 26px rgba(23, 92, 211, 0.08);
            }

            .ai-analysis-head {
                display: flex;
                flex-wrap: wrap;
                align-items: flex-start;
                justify-content: space-between;
                gap: 0.75rem;
                margin-bottom: 0.55rem;
            }

            .ai-analysis-title {
                color: var(--desk-navy);
                font-size: 1rem;
                font-weight: 820;
                line-height: 1.15;
            }

            .ai-analysis-subtitle {
                color: var(--desk-muted);
                font-size: 0.82rem;
                line-height: 1.35;
                margin-top: 0.18rem;
            }

            .ai-ticker-card {
                background: #ffffff;
                border: 1px solid var(--desk-line);
                border-left: 4px solid var(--desk-blue);
                border-radius: 8px;
                padding: 0.85rem 0.9rem;
                margin: 0.65rem 0;
                box-shadow: var(--desk-shadow-soft);
            }

            .ai-ticker-card.ai-yes { border-left-color: var(--desk-green); background: #f6fef9; }
            .ai-ticker-card.ai-careful { border-left-color: var(--desk-amber); background: #fffbeb; }
            .ai-ticker-card.ai-no { border-left-color: var(--desk-red); background: #fff5f5; }

            .ai-ticker-head {
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 0.6rem;
                margin-bottom: 0.55rem;
            }

            .ai-ticker-symbol {
                color: var(--desk-navy);
                font-size: 1.2rem;
                font-weight: 850;
                line-height: 1;
            }

            .ai-ticker-news {
                color: #344054;
                font-size: 0.84rem;
                line-height: 1.35;
                margin-top: 0.28rem;
                overflow-wrap: anywhere;
            }

            .ai-badge {
                border: 1px solid var(--desk-line);
                border-radius: 999px;
                padding: 0.28rem 0.5rem;
                color: #344054;
                background: #ffffff;
                font-size: 0.75rem;
                font-weight: 780;
                white-space: nowrap;
            }

            .ai-badge.ai-yes { color: var(--desk-green); border-color: #a6f4c5; background: #ecfdf3; }
            .ai-badge.ai-careful { color: var(--desk-amber); border-color: #fedf89; background: #fffaeb; }
            .ai-badge.ai-no { color: var(--desk-red); border-color: #fecdca; background: #fff1f0; }

            .ai-ticker-grid {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.55rem;
                margin: 0.5rem 0;
            }

            .ai-ticker-grid > div {
                background: #ffffff;
                border: 1px solid rgba(208, 213, 221, 0.82);
                border-radius: 8px;
                padding: 0.55rem 0.62rem;
                min-width: 0;
            }

            .ai-ticker-grid span {
                display: block;
                color: var(--desk-muted);
                font-size: 0.66rem;
                font-weight: 800;
                letter-spacing: 0.04em;
                text-transform: uppercase;
                margin-bottom: 0.25rem;
            }

            .ai-ticker-grid strong,
            .ai-verdict {
                color: var(--desk-ink);
                font-size: 0.84rem;
                line-height: 1.35;
                overflow-wrap: anywhere;
            }

            .ai-verdict {
                margin-top: 0.52rem;
            }

            div[class*="st-key-chart_card_"] {
                border: 2px solid var(--desk-blue) !important;
                border-radius: 8px !important;
                background: #ffffff !important;
                box-shadow: var(--desk-shadow) !important;
                margin-bottom: 0.95rem !important;
            }

            div[data-testid="stVerticalBlock"][class*="st-key-chart_card_"] {
                border-color: var(--desk-blue) !important;
            }

            div[class*="st-key-chart_card_"]:has(.pattern-card-new) {
                border-color: var(--desk-red) !important;
                box-shadow: 0 12px 32px rgba(180, 35, 24, 0.14) !important;
            }

            div[data-testid="stVerticalBlock"][class*="st-key-chart_card_"]:has(.pattern-card-new) {
                border-color: var(--desk-red) !important;
            }

            .pattern-chart-shell {
                padding: 0.12rem 0.02rem 0;
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
                margin-bottom: 0.35rem;
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

            .pattern-chart-svg svg {
                display: block;
                width: 100%;
                aspect-ratio: 2.1 / 1;
                object-fit: contain;
                border: 1px solid #eef2f6;
                border-radius: 8px;
                background: #ffffff;
            }

            .pattern-chart-action-row {
                display: flex;
                justify-content: flex-end;
                margin: 0.1rem 0 0.5rem;
            }

            .pattern-chart-stack {
                display: grid;
                grid-template-columns: 1fr;
                gap: 0.62rem;
            }

            .pattern-chart-panel {
                min-width: 0;
            }

            .pattern-chart-panel-title {
                color: var(--desk-muted);
                font-size: 0.68rem;
                font-weight: 820;
                letter-spacing: 0.05em;
                text-transform: uppercase;
                margin: 0.1rem 0 0.25rem;
            }

            .market-overview {
                background: #ffffff;
                border: 1px solid var(--desk-line);
                border-radius: 8px;
                padding: 0.75rem 0.85rem 0.85rem;
                margin: 0 0 0.85rem;
                box-shadow: var(--desk-shadow-soft);
            }

            .market-title {
                color: var(--desk-muted);
                font-size: 0.72rem;
                font-weight: 820;
                letter-spacing: 0.06em;
                text-transform: uppercase;
                margin-bottom: 0.55rem;
            }

            .market-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.6rem;
            }

            .market-card {
                border: 1px solid #e4e7ec;
                border-radius: 8px;
                background: #f8fafc;
                padding: 0.55rem;
                min-width: 0;
            }

            .market-card-head {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 0.6rem;
                margin-bottom: 0.35rem;
            }

            .market-symbol {
                color: var(--desk-navy);
                font-size: 1.02rem;
                font-weight: 840;
                line-height: 1.1;
            }

            .market-change {
                font-size: 0.82rem;
                font-weight: 820;
                line-height: 1.1;
                text-align: right;
                white-space: nowrap;
            }

            .market-change span {
                color: var(--desk-muted);
                font-size: 0.7rem;
                font-weight: 700;
            }

            .market-change.up { color: var(--desk-green); }
            .market-change.down { color: var(--desk-red); }
            .market-change.flat { color: var(--desk-muted); }

            .market-chart svg {
                display: block;
                width: 100%;
                aspect-ratio: 2.1 / 1;
                object-fit: contain;
                border-radius: 7px;
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
                header[data-testid="stHeader"] {
                    height: 3rem !important;
                    min-height: 3rem !important;
                }

                section[data-testid="stSidebar"] {
                    z-index: 999999;
                }

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

                .ai-ticker-grid {
                    grid-template-columns: 1fr;
                }

                .market-grid {
                    grid-template-columns: 1fr;
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
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }

                .ai-analysis-head,
                .ai-ticker-head {
                    flex-direction: column;
                }

                .ai-badge {
                    align-self: flex-start;
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
ALPACA_CACHE_TTL_SEC = 10
YAHOO_CACHE_TTL_SEC = 60
BATCH_SIZE = 120
ALPACA_SIP_DELAY_MINUTES = 16
MAX_BARS_PAGES = 25
AUTO_SCAN_MARKET_LIMIT = 10_000
CONTINUOUS_AUTO_REFRESH_SECONDS = 5
AUTO_SCAN_STALE_RUNNING_MINUTES = 30
CHART_VISIBLE_CANDLES = 60
MINUTE_CHART_VISIBLE_CANDLES = 500
DISMISS_TTL_HOURS = 7

DATA_SOURCE_AUTO = "AUTO_ALPACA_SIP_YAHOO"
DATA_SOURCE_ALPACA_SIP = "ALPACA_SIP"
DATA_SOURCE_YAHOO = "YAHOO"
DATA_SOURCE_LABELS = {
    DATA_SOURCE_AUTO: "Alpaca SIP → Yahoo резерв",
    DATA_SOURCE_ALPACA_SIP: "Только Alpaca SIP",
    DATA_SOURCE_YAHOO: "Yahoo Finance",
}

SIG_BASE = "BASE_VOLUME_EXPLOSION"
SIG_RVOL = "RELATIVE_VOLUME"
SIG_VCP = "VCP_SQUEEZE"
SIG_SPRING = "SPRING_REVERSAL"
SIG_MOMENTUM = "MOMENTUM_PULSE"

SCANNER_BASE = "BASE_VOLUME"
SCANNER_RVOL = "RELATIVE_VOLUME"
SCANNER_VCP = "VCP_SQUEEZE"
SCANNER_SPRING = "SPRING_REVERSAL"
SCANNER_MOMENTUM = "MOMENTUM_PULSE"

MOMENTUM_DIR_BOTH = "BOTH"
MOMENTUM_DIR_UP = "UP"
MOMENTUM_DIR_DOWN = "DOWN"
MOMENTUM_DIRECTION_LABELS = {
    "Вверх и вниз": MOMENTUM_DIR_BOTH,
    "Только вверх": MOMENTUM_DIR_UP,
    "Только вниз": MOMENTUM_DIR_DOWN,
}

SCANNER_LABELS = {
    SCANNER_BASE: "Взрыв из базы",
    SCANNER_RVOL: "Относительный объём RW",
    SCANNER_VCP: "VCP-сжатие",
    SCANNER_SPRING: "Spring-отскок",
    SCANNER_MOMENTUM: "Импульс + объём",
}
SCANNER_HELP = {
    SCANNER_BASE: (
        "Ищет твой старый паттерн: сегодняшнее открытие внутри вчерашней свечи, "
        "а сегодняшний объём выше максимального объёма среди предыдущих свечей."
    ),
    SCANNER_RVOL: (
        "Ищет акции, где сегодняшний объём резко выше средней за выбранное число дней. "
        "Это классический фильтр RW/RVOL: бумага сейчас в игре."
    ),
    SCANNER_VCP: (
        "Ищет сжатие перед движением: диапазон свечей постепенно становится уже, "
        "объём сохнет, цена находится близко к верхней границе базы."
    ),
    SCANNER_SPRING: (
        "Ищет ложный прокол поддержки: цена сходила ниже важного минимума, "
        "но закрылась обратно выше поддержки на повышенном объёме."
    ),
    SCANNER_MOMENTUM: (
        "Интрадей-скринер для day trading: ищет акции, где прямо сейчас появился "
        "быстрый рост или падение на повышенном минутном объёме."
    ),
}
SCANNER_SUBTITLES = {
    SCANNER_BASE: "Полный рынок · открытие внутри вчерашней свечи · объём выше всей базы",
    SCANNER_RVOL: "Полный рынок · сегодняшний объём против средней за N дней",
    SCANNER_VCP: "Полный рынок · сжатие диапазона · сухой объём · цена рядом с верхом базы",
    SCANNER_SPRING: "Полный рынок · прокол поддержки · возврат над уровень · объёмный отскок",
    SCANNER_MOMENTUM: "Полный рынок · 1Min Alpaca · быстрый импульс 5/15 мин · объёмный всплеск",
}

SIGNAL_LABELS = {
    SIG_BASE: "ВЗРЫВ ОБЪЁМА ИЗ БАЗЫ",
    SIG_RVOL: "ОТНОСИТЕЛЬНЫЙ ОБЪЁМ RW",
    SIG_VCP: "VCP-СЖАТИЕ",
    SIG_SPRING: "SPRING ОТ ДНА",
    SIG_MOMENTUM: "ИМПУЛЬС + ОБЪЁМ",
}
SIGNAL_SHORT_LABELS = {
    SIG_BASE: "Взрыв базы",
    SIG_RVOL: "RW объём",
    SIG_VCP: "VCP-сжатие",
    SIG_SPRING: "Spring от дна",
    SIG_MOMENTUM: "Импульс",
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

AI_PLACEHOLDER_SECRETS = {
    "",
    "PASTE_CLAUDE_API_KEY_HERE",
    "PASTE_GROK_XAI_API_KEY_HERE",
    "YOUR_ANTHROPIC_API_KEY",
    "YOUR_XAI_API_KEY",
}
AI_CLAUDE_KEY = secret_or_default("ANTHROPIC_API_KEY")
AI_GROK_KEY = secret_or_default("XAI_API_KEY")
AI_CLAUDE_MODEL_SETTING = secret_or_default("CLAUDE_MODEL", "auto")
AI_GROK_MODEL_SETTING = secret_or_default("GROK_MODEL", "auto")
AI_CLAUDE_FALLBACK_MODEL = secret_or_default("CLAUDE_FALLBACK_MODEL", "claude-fable-5")
AI_GROK_FALLBACK_MODEL = secret_or_default("GROK_FALLBACK_MODEL", "grok-4.3")
AI_CLAUDE_FAMILY_PRIORITY = [
    part.strip().lower()
    for part in secret_or_default("CLAUDE_FAMILY_PRIORITY", "hable,fable,opus,sonnet,haiku").split(",")
    if part.strip()
]
AI_ALLOW_LIMITED_CLAUDE_MODELS = secret_or_default("AI_ALLOW_LIMITED_CLAUDE_MODELS", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
AI_GROK_WEB_SEARCH_DEFAULT = secret_or_default("GROK_WEB_SEARCH", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
AI_CLAUDE_MAX_TOKENS = 2500
AI_GROK_MAX_TOKENS = 4000
AI_SYNTHESIS_MAX_TOKENS = 2500
AI_DEFAULT_TICKER_LIMIT = 10

AI_CLAUDE_PROMPT = """
Ты — строгий риск-фильтр для day/swing трейдинга.
Сначала проанализируй фундаментал полноценно, но ответ дай очень коротко.
По каждому тикеру дай только то, что может помешать входу сейчас или overnight:
- dilution / offering / ATM / S-1;
- delisting / compliance / reverse split;
- слабый cash runway / going concern;
- плохая отчётность или критический долг;
- если серьёзных красных флагов не видно, напиши "красных флагов нет".

Формат по каждому тикеру, очень коротко:
Тикер: <TICKER>
Риск-фильтр: <3-10 слов>
Фундаментальный стоп: <Да / Нет / Неясно>
"""

AI_GROK_SENTIMENT_PROMPT = """
Ты — эксперт по новостному импульсу и рыночному сентименту.
Проанализируй каждый тикер, который пришёл из моего торгового скринера.

Задача:
- сделать полный внутренний анализ новости, реакции цены, объёма и настроения рынка;
- найти реальную причину резкого объёма по каждому тикеру;
- указать точную дату новости/катализатора;
- определить, новость хорошая или плохая для цены;
- оценить, поддерживает ли новость текущий тренд;
- оценить силу катализатора и реакцию рынка;
- оценить настроение рынка прямо сейчас;
- понять сторону сделки: Long / Short / Нет;
- понять, есть ли смысл входить сейчас;
- отдельно понять, можно ли держать overnight.

Особенно ищи:
- новости FDA/clinical trial;
- earnings/guidance;
- offering/S-1/ATM/dilution;
- reverse split;
- delisting/compliance notice;
- contract/partnership;
- merger/acquisition;
- short squeeze/social momentum;
- sympathy move без реальной новости.

Если точную причину найти нельзя, честно напиши:
"точный катализатор не подтверждён".

Формат ответа:
По каждому тикеру очень коротко:
Тикер: <TICKER>
Новость: <5-10 слов + дата если есть>
Сила новости: <1-5>
Моментум: <Сильный / Средний / Слабый>
Настроение: <Бычье / Нейтральное / Медвежье>
Сторона: <Long / Short / Нет>
Вход сейчас: <Вход / Осторожно / Нет>
Overnight: <Да / Осторожно / Нет>
"""

AI_FINAL_SYNTHESIS_PROMPT_TEMPLATE = """
Ты — Grok. Ниже два анализа одного и того же списка тикеров из торгового скринера.

ОБЯЗАТЕЛЬНЫЙ СПИСОК ТИКЕРОВ:
{ticker_list}

Claude дал короткий риск-фильтр.
Grok дал новости, сентимент, моментум и катализаторы.

Твоя задача: сделать ультракороткий трейдерский итог строго по каждому тикеру.
Анализируй только тикеры из ОБЯЗАТЕЛЬНОГО СПИСКА.
Не заменяй тикер похожей компанией.
Не добавляй другие тикеры.
Если Claude или Grok случайно написал про другой тикер, игнорируй этот фрагмент.
Если по точному тикеру нет подтверждённой новости, так и напиши.
Не пиши длинные объяснения. Не добавляй лишних разделов.
Цель: быстро понять, что сегодня лучше всего по новостям и можно ли входить/держать overnight.
Главный вес: реальная новость, сила катализатора, объёмная реакция, моментум, настроение рынка.
Оценивай обе стороны:
- Long = хорошая новость, рынок поддерживает рост, тренд может продолжиться вверх.
- Short = плохая новость, рынок поддерживает падение, тренд может продолжиться вниз.
- Нет = нет понятной новости, слабый моментум или высокий риск.
Фундаментал Claude используй как риск-фильтр, а не как главный фактор.
Сделай полный внутренний анализ, но наружу выведи только короткое решение.
Если данные противоречат друг другу, выбирай более осторожный вариант и явно отметь риск.
Если дата новости не подтверждена, так и напиши.
Отсортируй все тикеры сверху вниз:
1. Самые сильные actionable идеи Long или Short с подтверждённой новостью.
2. Потом идеи, где новость есть, но риск/моментум хуже.
3. Внизу слабые, сомнительные или без подтверждённой новости.
Пиши максимально коротко:
- причина/новость: 5-10 слов, только суть;
- сторона: Long / Short / Нет;
- вход сейчас: Вход / Осторожно / Нет;
- overnight: Да / Осторожно / Нет;
- риск: 3-8 слов;
- вердикт: 5-12 слов;
- никаких абзацев, рассуждений и длинных новостей.

Строгий формат для каждого тикера:

Тикер: <TICKER>
Главная причина / новость (с датой): <5-10 слов>
Сила катализатора: ★★★★★
Сторона: <Long / Short / Нет>
Вход сейчас: <Вход / Осторожно / Нет>
Overnight: <Да / Осторожно / Нет>
Главные риски: <3-8 слов>
Короткий вердикт: <5-12 слов, почему входить или пропустить>

---

ОТВЕТ CLAUDE:
{claude_answer}

ОТВЕТ GROK:
{grok_answer}
"""


@dataclass(frozen=True)
class ScanConfig:
    scanner_mode: str = SCANNER_BASE
    min_dollar_volume: int = 250_000

    base_impulse_enabled: bool = True
    base_impulse_days: int = 10
    base_width_filter_enabled: bool = True
    base_max_width_pct: float = 40.0
    base_volume_mult: float = 2.0
    base_impulse_only: bool = False

    max_stale_days: int = 5
    min_price: float = 0.5
    max_price: float = 20.0

    rvol_avg_days: int = 30
    rvol_mult: float = 2.0

    vcp_days: int = 60
    vcp_max_base_width_pct: float = 30.0
    vcp_max_recent_width_pct: float = 10.0
    vcp_min_compression_pct: float = 35.0
    vcp_near_high_pct: float = 10.0
    vcp_dry_volume_ratio: float = 0.80

    spring_support_days: int = 60
    spring_low_days: int = 120
    spring_break_pct: float = 0.7
    spring_reclaim_pct: float = 0.2
    spring_close_position_pct: float = 60.0
    spring_volume_mult: float = 1.2
    spring_max_from_low_pct: float = 30.0

    momentum_direction: str = MOMENTUM_DIR_BOTH
    momentum_fast_minutes: int = 3
    momentum_confirm_minutes: int = 10
    momentum_volume_baseline_minutes: int = 60
    momentum_min_fast_move_pct: float = 0.7
    momentum_min_confirm_move_pct: float = 1.2
    momentum_volume_mult: float = 6.0
    momentum_confirm_volume_mult: float = 3.0
    momentum_min_5m_dollar_volume: int = 500_000
    momentum_min_15m_dollar_volume: int = 1_250_000
    momentum_min_day_dollar_volume: int = 3_000_000
    momentum_max_bar_age_minutes: int = 2
    momentum_max_vwap_distance_pct: float = 5.0
    momentum_require_vwap_side: bool = True
    momentum_require_ema_trend: bool = True
    momentum_include_extended_hours: bool = False
    momentum_min_score: int = 85
    momentum_min_quality_checks: int = 3
    momentum_require_new_volume_wave: bool = True
    momentum_min_volume_acceleration: float = 2.0
    momentum_max_prior_fast_rvol: float = 2.5
    momentum_max_recent_prior_rvol: float = 4.0
    momentum_min_fast_volume_share_pct: float = 40.0
    momentum_max_confirm_move_pct: float = 8.0


def now_et() -> datetime:
    return datetime.now(MARKET_TZ)


def now_et_str(fmt: str = "%H:%M:%S ET") -> str:
    return now_et().strftime(fmt)


def format_elapsed_since(started_at: datetime | None) -> str:
    if not started_at:
        return "0 сек"
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=MARKET_TZ)
    seconds = elapsed_seconds_since(started_at)
    minutes, seconds = divmod(seconds, 60)
    if minutes:
        return f"{minutes} мин {seconds:02d} сек"
    return f"{seconds} сек"


def elapsed_seconds_since(started_at: datetime | None) -> int:
    if not started_at:
        return 0
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=MARKET_TZ)
    return max(0, int((now_et() - started_at.astimezone(MARKET_TZ)).total_seconds()))


def format_seconds(seconds: Any) -> str:
    try:
        total = max(0, int(seconds))
    except (TypeError, ValueError):
        total = 0
    minutes, seconds = divmod(total, 60)
    if minutes:
        return f"{minutes} мин {seconds:02d} сек"
    return f"{seconds} сек"


def elapsed_scan_suffix(started_at: datetime | None) -> str:
    return f" · прошло: {format_elapsed_since(started_at)}"


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


def is_extended_session_timestamp(value: Any) -> bool:
    try:
        ts = pd.Timestamp(value)
    except Exception:
        return False
    if pd.isna(ts):
        return False
    if ts.tzinfo is None:
        ts = ts.tz_localize(MARKET_TZ)
    else:
        ts = ts.tz_convert(MARKET_TZ)
    minute = ts.hour * 60 + ts.minute
    return minute < 9 * 60 + 30 or minute >= 16 * 60


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
def alpaca_mode_label(realtime: bool) -> str:
    if realtime:
        return "Alpaca SIP real-time"
    return f"Alpaca SIP задержка {ALPACA_SIP_DELAY_MINUTES} мин"


def alpaca_sip_end_utc(realtime: bool = True) -> datetime:
    end_dt = datetime.now(timezone.utc).replace(microsecond=0)
    if realtime:
        return end_dt
    return end_dt - timedelta(minutes=ALPACA_SIP_DELAY_MINUTES)


def rfc3339_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def yahoo_period_for_days(days: int) -> str:
    if days <= 20:
        return "90d"
    if days <= 120:
        return "6mo"
    if days <= 240:
        return "1y"
    return "2y"


@st.cache_data(ttl=ALPACA_CACHE_TTL_SEC, show_spinner=False)
def fetch_alpaca_sip_batch(symbols: tuple[str, ...], days: int, realtime: bool = True) -> dict[str, pd.DataFrame]:
    if not ALPACA_KEY or not ALPACA_SECRET or not symbols:
        return {}

    source_label = alpaca_mode_label(realtime)
    end_dt = alpaca_sip_end_utc(realtime)
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
                LOGGER.info("%s auth/permission failed with status %s.", source_label, resp.status_code)
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
            LOGGER.info("%s pagination stopped after %s pages.", source_label, MAX_BARS_PAGES)
    except Exception as exc:
        LOGGER.info("%s batch failed: %s", source_label, exc)
        return {}

    out: dict[str, pd.DataFrame] = {}
    for symbol, rows in bars_by_symbol.items():
        if not rows:
            continue
        normalized = normalize_ohlcv(pd.DataFrame(rows), source_label)
        if normalized is not None and len(normalized) >= days + 2:
            out[symbol] = normalized
    return out


@st.cache_data(ttl=YAHOO_CACHE_TTL_SEC, show_spinner=False)
def fetch_yahoo_daily(ticker: str, days: int) -> pd.DataFrame | None:
    if yf is None:
        return None

    period = yahoo_period_for_days(days)
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


@st.cache_data(ttl=YAHOO_CACHE_TTL_SEC, show_spinner=False)
def fetch_yahoo_batch(symbols: tuple[str, ...], days: int) -> dict[str, pd.DataFrame]:
    if yf is None or not symbols:
        return {}

    period = yahoo_period_for_days(days)
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


def required_history_days(cfg: ScanConfig) -> int:
    if cfg.scanner_mode == SCANNER_RVOL:
        return max(int(cfg.rvol_avg_days), 5, CHART_VISIBLE_CANDLES)
    if cfg.scanner_mode == SCANNER_VCP:
        return max(int(cfg.vcp_days), 30, CHART_VISIBLE_CANDLES)
    if cfg.scanner_mode == SCANNER_SPRING:
        return max(int(cfg.spring_support_days), int(cfg.spring_low_days), 60, CHART_VISIBLE_CANDLES)
    return max(int(cfg.base_impulse_days), 5, CHART_VISIBLE_CANDLES)


def load_bars(
    ticker_infos: list[dict[str, Any]],
    cfg: ScanConfig,
    data_source: str,
    alpaca_realtime: bool,
    progress_box: Any,
    status_box: Any,
    scan_started_at: datetime | None = None,
) -> dict[str, pd.DataFrame]:
    symbols = [str(item["ticker"]).upper() for item in ticker_infos]
    bars: dict[str, pd.DataFrame] = {}
    history_days = required_history_days(cfg)

    if data_source in {DATA_SOURCE_ALPACA_SIP, DATA_SOURCE_AUTO} and not (ALPACA_KEY and ALPACA_SECRET):
        status_box.caption(f"{alpaca_mode_label(alpaca_realtime)} недоступен: нет ALPACA_KEY / ALPACA_SECRET.{elapsed_scan_suffix(scan_started_at)}")
        if data_source == DATA_SOURCE_ALPACA_SIP:
            return bars

    if data_source in {DATA_SOURCE_YAHOO, DATA_SOURCE_AUTO} and yf is None:
        status_box.caption(f"Yahoo Finance недоступен: пакет yfinance не установлен.{elapsed_scan_suffix(scan_started_at)}")
        if data_source == DATA_SOURCE_YAHOO:
            return bars

    batches = list(chunks(symbols, BATCH_SIZE))
    if data_source in {DATA_SOURCE_ALPACA_SIP, DATA_SOURCE_AUTO} and ALPACA_KEY and ALPACA_SECRET:
        alpaca_label = alpaca_mode_label(alpaca_realtime)
        for idx, batch in enumerate(batches, start=1):
            status_box.caption(
                f"Загружаю {alpaca_label} · "
                f"пачка {idx}/{len(batches)} · готово: {len(bars)}"
                f"{elapsed_scan_suffix(scan_started_at)}"
            )
            bars.update(fetch_alpaca_sip_batch(tuple(batch), history_days, alpaca_realtime))
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
            f"{elapsed_scan_suffix(scan_started_at)}"
        )
        bars.update(fetch_yahoo_batch(tuple(batch), history_days))
        progress_box.progress(0.55 + 0.15 * idx / max(len(yahoo_batches), 1))

    progress_box.progress(0.7)
    return bars


@st.cache_data(ttl=ALPACA_CACHE_TTL_SEC, show_spinner=False)
def fetch_alpaca_minute_bars_batch(
    symbols: tuple[str, ...],
    count: int = MINUTE_CHART_VISIBLE_CANDLES,
    realtime: bool = True,
) -> dict[str, pd.DataFrame]:
    clean_symbols = tuple(dict.fromkeys(str(symbol or "").upper().strip() for symbol in symbols if str(symbol or "").strip()))
    if not clean_symbols or not ALPACA_KEY or not ALPACA_SECRET:
        return {}

    end_dt = alpaca_sip_end_utc(realtime)
    start_dt = end_dt - timedelta(days=5)
    params = {
        "symbols": ",".join(clean_symbols),
        "timeframe": "1Min",
        "start": rfc3339_utc(start_dt),
        "end": rfc3339_utc(end_dt),
        "limit": 10000,
        "adjustment": "split",
        "feed": "sip",
        "sort": "asc",
    }

    bars_by_symbol: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in clean_symbols}
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
                LOGGER.info("Alpaca minute auth/permission failed: %s", resp.status_code)
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
            LOGGER.info("Alpaca minute pagination stopped after %s pages.", MAX_BARS_PAGES)
    except Exception as exc:
        LOGGER.info("Alpaca minute batch failed: %s", exc)
        return {}

    out: dict[str, pd.DataFrame] = {}
    source_label = f"{alpaca_mode_label(realtime)} 1Min"
    for symbol, rows in bars_by_symbol.items():
        if not rows:
            continue
        normalized = normalize_ohlcv(pd.DataFrame(rows), source_label)
        if normalized is not None and len(normalized) >= 2:
            out[symbol] = normalized.tail(max(2, int(count)))
    return out


def fetch_alpaca_minute_bars(
    ticker: str,
    count: int = MINUTE_CHART_VISIBLE_CANDLES,
    realtime: bool = True,
) -> pd.DataFrame | None:
    symbol = str(ticker or "").upper().strip()
    if not symbol:
        return None
    return fetch_alpaca_minute_bars_batch((symbol,), count, realtime).get(symbol)


@st.cache_data(ttl=ALPACA_CACHE_TTL_SEC, show_spinner=False)
def fetch_alpaca_intraday_bars_batch(
    symbols: tuple[str, ...],
    start_iso: str,
    end_iso: str,
    realtime: bool = True,
) -> dict[str, pd.DataFrame]:
    clean_symbols = tuple(dict.fromkeys(str(symbol or "").upper().strip() for symbol in symbols if str(symbol or "").strip()))
    if not clean_symbols or not ALPACA_KEY or not ALPACA_SECRET:
        return {}

    params = {
        "symbols": ",".join(clean_symbols),
        "timeframe": "1Min",
        "start": start_iso,
        "end": end_iso,
        "limit": 10000,
        "adjustment": "split",
        "feed": "sip",
        "sort": "asc",
    }

    bars_by_symbol: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in clean_symbols}
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
                LOGGER.info("Alpaca intraday auth/permission failed: %s", resp.status_code)
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
            LOGGER.info("Alpaca intraday pagination stopped after %s pages.", MAX_BARS_PAGES)
    except Exception as exc:
        LOGGER.info("Alpaca intraday batch failed: %s", exc)
        return {}

    out: dict[str, pd.DataFrame] = {}
    source_label = f"{alpaca_mode_label(realtime)} 1Min"
    for symbol, rows in bars_by_symbol.items():
        if not rows:
            continue
        normalized = normalize_ohlcv(pd.DataFrame(rows), source_label)
        if normalized is not None and len(normalized) >= 2:
            out[symbol] = normalized
    return out


def intraday_scan_window(cfg: ScanConfig, alpaca_realtime: bool) -> tuple[datetime, datetime]:
    end_utc = alpaca_sip_end_utc(alpaca_realtime)
    end_et = end_utc.astimezone(MARKET_TZ)
    open_hour = 4 if cfg.momentum_include_extended_hours else 9
    open_minute = 0 if cfg.momentum_include_extended_hours else 30
    session_start_et = end_et.replace(hour=open_hour, minute=open_minute, second=0, microsecond=0)
    if end_et < session_start_et:
        lookback = max(
            90,
            int(cfg.momentum_volume_baseline_minutes)
            + int(cfg.momentum_confirm_minutes)
            + int(cfg.momentum_fast_minutes)
            + 30,
        )
        session_start_et = end_et - timedelta(minutes=lookback)
    return session_start_et.astimezone(timezone.utc), end_utc


def load_momentum_bars(
    ticker_infos: list[dict[str, Any]],
    cfg: ScanConfig,
    data_source: str,
    alpaca_realtime: bool,
    progress_box: Any,
    status_box: Any,
    scan_started_at: datetime | None = None,
) -> dict[str, pd.DataFrame]:
    bars: dict[str, pd.DataFrame] = {}
    if data_source not in {DATA_SOURCE_ALPACA_SIP, DATA_SOURCE_AUTO}:
        status_box.caption(f"Импульс + объём работает только через Alpaca SIP 1Min.{elapsed_scan_suffix(scan_started_at)}")
        progress_box.progress(0.7)
        return bars
    if not (ALPACA_KEY and ALPACA_SECRET):
        status_box.caption(f"Alpaca SIP 1Min недоступен: нет ALPACA_KEY / ALPACA_SECRET.{elapsed_scan_suffix(scan_started_at)}")
        progress_box.progress(0.7)
        return bars

    symbols = [str(item["ticker"]).upper() for item in ticker_infos]
    start_utc, end_utc = intraday_scan_window(cfg, alpaca_realtime)
    start_iso = rfc3339_utc(start_utc)
    end_iso = rfc3339_utc(end_utc)
    batches = list(chunks(symbols, 25))
    alpaca_label = alpaca_mode_label(alpaca_realtime)
    for idx, batch in enumerate(batches, start=1):
        status_box.caption(
            f"Загружаю {alpaca_label} 1Min · пачка {idx}/{len(batches)} · готово: {len(bars)}"
            f"{elapsed_scan_suffix(scan_started_at)}"
        )
        bars.update(fetch_alpaca_intraday_bars_batch(tuple(batch), start_iso, end_iso, alpaca_realtime))
        progress_box.progress(0.7 * idx / max(len(batches), 1))

    progress_box.progress(0.7)
    return bars


# ── SIGNAL LOGIC ──────────────────────────────────────────────────
@dataclass(frozen=True)
class BaseImpulse:
    low: float
    high: float
    width_pct: float
    vol_max: float
    vol_avg: float
    volume_mult: float
    move_pct: float
    body_pct: float


@dataclass(frozen=True)
class RvolSetup:
    low: float
    high: float
    width_pct: float
    avg_volume: float
    rvol: float
    dollar_volume: float
    move_pct: float
    range_days: int


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


@dataclass(frozen=True)
class MomentumPulse:
    direction: str
    price: float
    move_5m_pct: float
    move_15m_pct: float
    rvol_5m: float
    rvol_15m: float
    volume_5m: float
    volume_15m: float
    baseline_5m: float
    baseline_15m: float
    dollar_5m: float
    dollar_15m: float
    dollar_day: float
    vwap: float
    vwap_distance_pct: float
    ema9: float
    ema20: float
    bar_age_minutes: float
    breakout_confirmed: bool
    vwap_aligned: bool
    ema_aligned: bool
    directional_bars_confirmed: bool
    early_volume_wave: bool
    volume_acceleration: float
    prior_fast_rvol: float
    recent_prior_max_rvol: float
    fast_volume_share_pct: float
    multi_minute_volume_confirmed: bool
    quality_checks: int


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

    base_low = float(window["Low"].min())
    base_high = float(window["High"].max())
    if base_low <= 0 or base_high <= base_low:
        return None
    base_width_pct = (base_high - base_low) / base_low * 100
    if cfg.base_width_filter_enabled and cfg.base_max_width_pct > 0 and base_width_pct > cfg.base_max_width_pct:
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

    body_pct = abs(latest_close - latest_open) / latest_open * 100
    move_pct = (latest_close - latest_open) / latest_open * 100
    return BaseImpulse(
        low=base_low,
        high=base_high,
        width_pct=base_width_pct,
        vol_max=vol_max,
        vol_avg=vol_avg,
        volume_mult=volume_mult,
        move_pct=move_pct,
        body_pct=body_pct,
    )


def build_rvol_setup(df: pd.DataFrame, cfg: ScanConfig) -> RvolSetup | None:
    avg_days = int(cfg.rvol_avg_days)
    if avg_days < 5 or len(df) < avg_days + 2:
        return None

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    price = float(latest["Close"])
    volume = float(latest["Volume"])
    prev_close = float(prev["Close"])
    if price <= 0 or volume <= 0 or prev_close <= 0:
        return None

    avg_window = pd.to_numeric(df["Volume"].iloc[-(avg_days + 1) : -1], errors="coerce")
    avg_window = avg_window[avg_window > 0]
    if avg_window.empty:
        return None
    avg_volume = float(avg_window.mean())
    if avg_volume <= 0:
        return None

    rvol = volume / avg_volume
    if rvol < cfg.rvol_mult:
        return None

    range_days = min(avg_days, 24)
    range_window = df.iloc[-(range_days + 1) : -1].copy()
    low = float(pd.to_numeric(range_window["Low"], errors="coerce").min())
    high = float(pd.to_numeric(range_window["High"], errors="coerce").max())
    if low <= 0 or high <= low:
        return None

    move_pct = (price - prev_close) / prev_close * 100
    width_pct = (high - low) / low * 100
    return RvolSetup(
        low=low,
        high=high,
        width_pct=width_pct,
        avg_volume=avg_volume,
        rvol=rvol,
        dollar_volume=price * volume,
        move_pct=move_pct,
        range_days=range_days,
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


def momentum_intraday_frame(df: pd.DataFrame, cfg: ScanConfig, reference_time: datetime) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    data = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"]).copy()
    if data.empty or not isinstance(data.index, pd.DatetimeIndex):
        return pd.DataFrame()

    index = pd.DatetimeIndex(data.index)
    if index.tz is None:
        index = index.tz_localize(timezone.utc)
    index = index.tz_convert(MARKET_TZ)
    data.index = index

    ref_ts = pd.Timestamp(reference_time)
    if ref_ts.tzinfo is None:
        ref_ts = ref_ts.tz_localize(MARKET_TZ)
    else:
        ref_ts = ref_ts.tz_convert(MARKET_TZ)
    data = data[data.index <= ref_ts + pd.Timedelta(minutes=1)]

    if not cfg.momentum_include_extended_hours:
        minute_of_day = data.index.hour * 60 + data.index.minute
        data = data[(minute_of_day >= 9 * 60 + 30) & (minute_of_day < 16 * 60)]

    return data.sort_index()


def recent_intraday_window(df: pd.DataFrame, minutes: int) -> pd.DataFrame:
    if df.empty:
        return df
    latest_ts = df.index[-1]
    cutoff = latest_ts - pd.Timedelta(minutes=max(1, int(minutes)))
    return df[df.index >= cutoff]


def rolling_volume_baseline(prior: pd.DataFrame, window_minutes: int) -> float:
    if prior.empty:
        return 0.0
    volume = pd.to_numeric(prior["Volume"], errors="coerce").fillna(0)
    volume = volume[volume >= 0]
    if volume.empty:
        return 0.0

    window = max(1, int(window_minutes))
    min_periods = max(2, min(window, max(2, window // 2)))
    rolling = volume.rolling(window, min_periods=min_periods).sum().dropna()
    if not rolling.empty:
        return max(float(rolling.tail(30).median()), 1.0)

    positive = volume[volume > 0]
    if positive.empty:
        return 0.0
    return max(float(positive.tail(max(5, window)).median()) * window, 1.0)


def dollar_volume(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    close = pd.to_numeric(frame["Close"], errors="coerce").fillna(0)
    volume = pd.to_numeric(frame["Volume"], errors="coerce").fillna(0)
    return float((close * volume).sum())


def intraday_vwap(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    volume = pd.to_numeric(df["Volume"], errors="coerce").fillna(0)
    total_volume = float(volume.sum())
    if total_volume <= 0:
        return 0.0
    typical = (
        pd.to_numeric(df["High"], errors="coerce").fillna(0)
        + pd.to_numeric(df["Low"], errors="coerce").fillna(0)
        + pd.to_numeric(df["Close"], errors="coerce").fillna(0)
    ) / 3
    return float((typical * volume).sum() / total_volume)


def intraday_move_pct(frame: pd.DataFrame, latest_close: float) -> float:
    if frame.empty:
        return 0.0
    start_open = float(frame.iloc[0]["Open"])
    if start_open <= 0:
        return 0.0
    return (latest_close - start_open) / start_open * 100


def build_momentum_pulse(
    df: pd.DataFrame,
    cfg: ScanConfig,
    reference_time: datetime,
) -> MomentumPulse | None:
    data = momentum_intraday_frame(df, cfg, reference_time)
    min_bars = max(12, int(cfg.momentum_confirm_minutes))
    if len(data) < min_bars:
        return None

    latest_ts = data.index[-1]
    ref_ts = pd.Timestamp(reference_time)
    if ref_ts.tzinfo is None:
        ref_ts = ref_ts.tz_localize(MARKET_TZ)
    else:
        ref_ts = ref_ts.tz_convert(MARKET_TZ)
    bar_age_minutes = max(0.0, (ref_ts - latest_ts).total_seconds() / 60)
    if bar_age_minutes > cfg.momentum_max_bar_age_minutes:
        return None

    latest = data.iloc[-1]
    price = float(latest["Close"])
    if price <= 0:
        return None

    fast_window = recent_intraday_window(data, cfg.momentum_fast_minutes)
    confirm_window = recent_intraday_window(data, cfg.momentum_confirm_minutes)
    if len(fast_window) < max(3, min(int(cfg.momentum_fast_minutes), 4)):
        return None
    if len(confirm_window) < max(8, int(cfg.momentum_confirm_minutes * 0.55)):
        return None

    last_five = data.tail(5)
    if (pd.to_numeric(last_five["Volume"], errors="coerce").fillna(0) > 0).sum() < 3:
        return None

    baseline_start = fast_window.index[0]
    baseline_minutes = max(int(cfg.momentum_volume_baseline_minutes), int(cfg.momentum_confirm_minutes) * 2)
    prior = data[data.index < baseline_start].tail(baseline_minutes)
    if len(prior) < max(8, int(cfg.momentum_fast_minutes) * 2):
        return None

    volume_5m = float(pd.to_numeric(fast_window["Volume"], errors="coerce").fillna(0).sum())
    volume_15m = float(pd.to_numeric(confirm_window["Volume"], errors="coerce").fillna(0).sum())
    if volume_5m <= 0 or volume_15m <= 0:
        return None

    baseline_5m = rolling_volume_baseline(prior, cfg.momentum_fast_minutes)
    baseline_15m = rolling_volume_baseline(prior, cfg.momentum_confirm_minutes)
    if baseline_5m <= 0 or baseline_15m <= 0:
        return None

    rvol_5m = volume_5m / baseline_5m
    rvol_15m = volume_15m / baseline_15m
    if rvol_5m < cfg.momentum_volume_mult or rvol_15m < cfg.momentum_confirm_volume_mult:
        return None

    previous_fast_start = fast_window.index[0] - pd.Timedelta(minutes=max(1, int(cfg.momentum_fast_minutes)))
    previous_fast = data[(data.index < fast_window.index[0]) & (data.index >= previous_fast_start)]
    previous_fast_volume = float(pd.to_numeric(previous_fast["Volume"], errors="coerce").fillna(0).sum()) if not previous_fast.empty else 0.0
    prior_fast_rvol = previous_fast_volume / baseline_5m if baseline_5m > 0 else 0.0
    volume_acceleration_base = max(previous_fast_volume, baseline_5m / max(cfg.momentum_volume_mult, 1.0), 1.0)
    volume_acceleration = volume_5m / volume_acceleration_base
    recent_prior_start = fast_window.index[0] - pd.Timedelta(minutes=20)
    recent_prior = data[(data.index < fast_window.index[0]) & (data.index >= recent_prior_start)]
    recent_prior_max_rvol = 0.0
    if not recent_prior.empty:
        prior_volume_series = pd.to_numeric(recent_prior["Volume"], errors="coerce").fillna(0)
        prior_rolling = prior_volume_series.rolling(
            max(1, int(cfg.momentum_fast_minutes)),
            min_periods=max(1, min(2, int(cfg.momentum_fast_minutes))),
        ).sum().dropna()
        if not prior_rolling.empty and baseline_5m > 0:
            recent_prior_max_rvol = float(prior_rolling.max()) / baseline_5m
    fast_volume_share_pct = volume_5m / volume_15m * 100 if volume_15m > 0 else 0.0
    baseline_1m = baseline_5m / max(1, int(cfg.momentum_fast_minutes))
    last_three_volume = pd.to_numeric(data.tail(3)["Volume"], errors="coerce").fillna(0)
    multi_minute_volume_confirmed = bool((last_three_volume >= baseline_1m * 1.5).sum() >= 2)
    early_volume_wave = (
        volume_acceleration >= cfg.momentum_min_volume_acceleration
        and prior_fast_rvol <= cfg.momentum_max_prior_fast_rvol
        and recent_prior_max_rvol <= cfg.momentum_max_recent_prior_rvol
        and fast_volume_share_pct >= cfg.momentum_min_fast_volume_share_pct
        and multi_minute_volume_confirmed
    )
    if cfg.momentum_require_new_volume_wave and not early_volume_wave:
        return None

    move_5m = intraday_move_pct(fast_window, price)
    move_15m = intraday_move_pct(confirm_window, price)
    if cfg.momentum_max_confirm_move_pct > 0 and abs(move_15m) > cfg.momentum_max_confirm_move_pct:
        return None
    long_hit = move_5m >= cfg.momentum_min_fast_move_pct and move_15m >= cfg.momentum_min_confirm_move_pct
    short_hit = move_5m <= -cfg.momentum_min_fast_move_pct and move_15m <= -cfg.momentum_min_confirm_move_pct
    if cfg.momentum_direction == MOMENTUM_DIR_UP:
        short_hit = False
    elif cfg.momentum_direction == MOMENTUM_DIR_DOWN:
        long_hit = False
    if not (long_hit or short_hit):
        return None

    direction = MOMENTUM_DIR_UP if long_hit and abs(move_5m) >= abs(move_15m) * 0.35 else MOMENTUM_DIR_DOWN
    if long_hit and not short_hit:
        direction = MOMENTUM_DIR_UP
    elif short_hit and not long_hit:
        direction = MOMENTUM_DIR_DOWN

    dollar_5m = dollar_volume(fast_window)
    dollar_15m = dollar_volume(confirm_window)
    dollar_day = dollar_volume(data)
    if dollar_5m < cfg.momentum_min_5m_dollar_volume:
        return None
    if dollar_15m < cfg.momentum_min_15m_dollar_volume:
        return None
    if dollar_day < cfg.momentum_min_day_dollar_volume:
        return None

    vwap = intraday_vwap(data)
    if vwap <= 0:
        return None
    vwap_distance_pct = (price - vwap) / vwap * 100
    if cfg.momentum_max_vwap_distance_pct > 0 and abs(vwap_distance_pct) > cfg.momentum_max_vwap_distance_pct:
        return None

    close_series = pd.to_numeric(data["Close"], errors="coerce").dropna()
    if close_series.empty:
        return None
    ema9 = float(close_series.ewm(span=9, adjust=False).mean().iloc[-1])
    ema20 = float(close_series.ewm(span=20, adjust=False).mean().iloc[-1])
    vwap_aligned = price >= vwap if direction == MOMENTUM_DIR_UP else price <= vwap
    ema_aligned = ema9 >= ema20 if direction == MOMENTUM_DIR_UP else ema9 <= ema20
    if cfg.momentum_require_vwap_side and not vwap_aligned:
        return None
    if cfg.momentum_require_ema_trend and not ema_aligned:
        return None

    recent_directional = data.tail(5)
    green_count = int((pd.to_numeric(recent_directional["Close"], errors="coerce") > pd.to_numeric(recent_directional["Open"], errors="coerce")).sum())
    red_count = int((pd.to_numeric(recent_directional["Close"], errors="coerce") < pd.to_numeric(recent_directional["Open"], errors="coerce")).sum())
    fast_low = float(pd.to_numeric(fast_window["Low"], errors="coerce").min())
    fast_high = float(pd.to_numeric(fast_window["High"], errors="coerce").max())
    fast_span = fast_high - fast_low
    if fast_span <= 0:
        return None
    close_position = (price - fast_low) / fast_span * 100
    if direction == MOMENTUM_DIR_UP:
        directional_bars_confirmed = green_count >= 3 and close_position >= 60
    else:
        directional_bars_confirmed = red_count >= 3 and close_position <= 40

    prior_20 = data.iloc[:-1].tail(20)
    breakout_confirmed = False
    if not prior_20.empty:
        prior_high = float(pd.to_numeric(prior_20["High"], errors="coerce").max())
        prior_low = float(pd.to_numeric(prior_20["Low"], errors="coerce").min())
        if direction == MOMENTUM_DIR_UP and prior_high > 0:
            breakout_confirmed = price >= prior_high * 1.002
        elif direction == MOMENTUM_DIR_DOWN and prior_low > 0:
            breakout_confirmed = price <= prior_low * 0.998

    quality_checks = sum(
        1
        for passed in (
            vwap_aligned,
            ema_aligned,
            breakout_confirmed,
            directional_bars_confirmed,
            early_volume_wave,
            abs(vwap_distance_pct) <= 4.0,
        )
        if passed
    )
    if quality_checks < cfg.momentum_min_quality_checks:
        return None

    return MomentumPulse(
        direction=direction,
        price=price,
        move_5m_pct=move_5m,
        move_15m_pct=move_15m,
        rvol_5m=rvol_5m,
        rvol_15m=rvol_15m,
        volume_5m=volume_5m,
        volume_15m=volume_15m,
        baseline_5m=baseline_5m,
        baseline_15m=baseline_15m,
        dollar_5m=dollar_5m,
        dollar_15m=dollar_15m,
        dollar_day=dollar_day,
        vwap=vwap,
        vwap_distance_pct=vwap_distance_pct,
        ema9=ema9,
        ema20=ema20,
        bar_age_minutes=bar_age_minutes,
        breakout_confirmed=breakout_confirmed,
        vwap_aligned=vwap_aligned,
        ema_aligned=ema_aligned,
        directional_bars_confirmed=directional_bars_confirmed,
        early_volume_wave=early_volume_wave,
        volume_acceleration=volume_acceleration,
        prior_fast_rvol=prior_fast_rvol,
        recent_prior_max_rvol=recent_prior_max_rvol,
        fast_volume_share_pct=fast_volume_share_pct,
        multi_minute_volume_confirmed=multi_minute_volume_confirmed,
        quality_checks=quality_checks,
    )


def pattern_chart_payload(
    df: pd.DataFrame,
    lookback: int,
    band_low: float | None = None,
    band_high: float | None = None,
    band_label: str = "зона сигнала",
    *,
    visible_candles: int = CHART_VISIBLE_CANDLES,
    band_days: int | None = None,
    timeframe: str = "D",
    show_default_band: bool = True,
) -> dict[str, Any]:
    candles = max(2, int(visible_candles))
    timeframe_code = str(timeframe or "D").upper()
    chart_df = df.dropna(subset=["Open", "High", "Low", "Close"]).tail(candles).copy()
    if chart_df.empty:
        return {}

    chart_df["Volume"] = pd.to_numeric(chart_df["Volume"], errors="coerce").fillna(0)
    chart_df["Open"] = pd.to_numeric(chart_df["Open"], errors="coerce")
    chart_df["High"] = pd.to_numeric(chart_df["High"], errors="coerce")
    chart_df["Low"] = pd.to_numeric(chart_df["Low"], errors="coerce")
    chart_df["Close"] = pd.to_numeric(chart_df["Close"], errors="coerce")
    chart_df = chart_df.dropna(subset=["Open", "High", "Low", "Close"])
    if chart_df.empty:
        return {}

    if show_default_band and (band_low is None or band_high is None):
        if len(chart_df) >= 2:
            prev = chart_df.iloc[-2]
            band_low = float(prev["Low"])
            band_high = float(prev["High"])

    rows = []
    for timestamp, row in chart_df.iterrows():
        rows.append(
            {
                "Open": float(row["Open"]),
                "High": float(row["High"]),
                "Low": float(row["Low"]),
                "Close": float(row["Close"]),
                "Volume": float(row["Volume"]),
                "Extended": bool(timeframe_code == "M" and is_extended_session_timestamp(timestamp)),
            }
        )

    return {
        "rows": rows,
        "band_low": band_low,
        "band_high": band_high,
        "band_label": band_label,
        "band_days": int(band_days if band_days is not None else lookback),
        "timeframe": timeframe_code,
        "required_visible_candles": candles if timeframe_code == "D" and candles >= CHART_VISIBLE_CANDLES else 0,
    }


def pattern_chart_svg(payload: dict[str, Any]) -> str:
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        return ""
    required_count = int(payload.get("required_visible_candles") or 0)
    if required_count and len(rows) < required_count:
        return ""

    width = 760
    height = 360
    pad_left = 34
    pad_right = 14
    price_top = 20
    price_bottom = 232
    volume_top = 260
    volume_bottom = 326
    plot_left = pad_left
    plot_right = width - pad_right
    plot_w = plot_right - plot_left
    price_h = price_bottom - price_top
    volume_h = volume_bottom - volume_top

    min_price = min(float(row["Low"]) for row in rows)
    max_price = max(float(row["High"]) for row in rows)
    band_low = payload.get("band_low")
    band_high = payload.get("band_high")
    if band_low and band_low > 0:
        min_price = min(min_price, float(band_low))
    if band_high and band_high > 0:
        max_price = max(max_price, float(band_high))
    if min_price <= 0 or max_price <= min_price:
        return ""
    price_span = max_price - min_price
    min_price = max(0.0001, min_price - price_span * 0.06)
    max_price = max_price + price_span * 0.08

    def y_pos(value: float) -> float:
        return price_top + (max_price - value) / (max_price - min_price) * price_h

    max_volume = max(float(row.get("Volume", 0)) for row in rows)
    if max_volume <= 0:
        max_volume = 1.0

    def vol_y(value: float) -> float:
        return volume_bottom - value / max_volume * volume_h

    count = len(rows)
    slot = plot_w / max(count, 1)
    if count >= 700:
        candle_w = max(0.45, min(1.1, slot * 0.72))
        wick_w = 0.62
    elif count >= 250:
        candle_w = max(0.9, min(2.2, slot * 0.64))
        wick_w = 0.85
    else:
        candle_w = max(2.6, min(8.0, slot * 0.58))
        wick_w = 1.25
    timeframe = html.escape(str(payload.get("timeframe") or "D"))
    last_close = float(rows[-1]["Close"])
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" rx="8" fill="#ffffff"/>',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="8" fill="none" stroke="#d8dde6"/>',
    ]

    extended_start: int | None = None
    for idx, row in enumerate(rows):
        is_extended = bool(row.get("Extended"))
        if is_extended and extended_start is None:
            extended_start = idx
        is_last = idx == count - 1
        if extended_start is not None and (not is_extended or is_last):
            extended_end = idx if is_extended and is_last else idx - 1
            x = plot_left + extended_start * slot
            w = (extended_end - extended_start + 1) * slot
            parts.append(
                f'<rect x="{x:.2f}" y="{price_top:.2f}" width="{w:.2f}" '
                f'height="{volume_bottom - price_top:.2f}" fill="#eef0f3" opacity="0.78"/>'
            )
            extended_start = None

    parts.extend([
        f'<line x1="{plot_left}" x2="{plot_right}" y1="{price_top}" y2="{price_top}" stroke="#edf2f7"/>',
        f'<line x1="{plot_left}" x2="{plot_right}" y1="{(price_top + price_bottom) / 2:.2f}" y2="{(price_top + price_bottom) / 2:.2f}" stroke="#edf2f7"/>',
        f'<line x1="{plot_left}" x2="{plot_right}" y1="{price_bottom}" y2="{price_bottom}" stroke="#d0d5dd"/>',
        f'<line x1="{plot_left}" x2="{plot_right}" y1="{volume_bottom}" y2="{volume_bottom}" stroke="#d0d5dd"/>',
        f'<text x="{plot_left}" y="15" fill="#667085" font-size="12" font-weight="700" font-family="Inter, Arial, sans-serif">{timeframe} · {len(rows)} свечей</text>',
        f'<text x="{plot_right}" y="15" fill="#344054" font-size="12" font-weight="800" font-family="Inter, Arial, sans-serif" text-anchor="end">${last_close:.4g}</text>',
    ])

    if band_low is not None and band_high is not None and band_high > band_low > 0:
        band_y = y_pos(float(band_high))
        band_h = max(1.0, y_pos(float(band_low)) - band_y)
        parts.append(f'<rect x="{plot_left:.2f}" y="{band_y:.2f}" width="{plot_w:.2f}" height="{band_h:.2f}" rx="4" fill="#dbeafe" opacity="0.22"/>')
        parts.append(
            f'<line x1="{plot_left}" x2="{plot_right}" y1="{band_y:.2f}" y2="{band_y:.2f}" '
            f'stroke="#175cd3" stroke-width="1.25" stroke-dasharray="5 4" opacity="0.86"/>'
        )
        parts.append(
            f'<line x1="{plot_left}" x2="{plot_right}" y1="{band_y + band_h:.2f}" y2="{band_y + band_h:.2f}" '
            f'stroke="#175cd3" stroke-width="1.25" stroke-dasharray="5 4" opacity="0.86"/>'
        )

    prior_volumes = [float(row.get("Volume", 0)) for row in rows[:-1]]
    if prior_volumes and max(prior_volumes) > 0:
        prior_max_y = vol_y(max(prior_volumes))
        parts.append(
            f'<line x1="{plot_left}" x2="{plot_right}" y1="{prior_max_y:.2f}" y2="{prior_max_y:.2f}" '
            f'stroke="#667085" stroke-width="1.3" stroke-dasharray="5 4"/>'
        )
        if count <= 250:
            parts.append(
                f'<text x="{plot_right}" y="{max(volume_top + 10, prior_max_y - 4):.2f}" fill="#667085" '
                f'font-size="10" font-weight="700" font-family="Inter, Arial, sans-serif" text-anchor="end">прошл. max volume</text>'
            )

    for idx, row in enumerate(rows, start=0):
        open_price = float(row["Open"])
        high_price = float(row["High"])
        low_price = float(row["Low"])
        close_price = float(row["Close"])
        volume = float(row.get("Volume", 0))
        x = plot_left + slot * (idx + 0.5)
        color = "#047857" if close_price >= open_price else "#b42318"
        y_high = y_pos(high_price)
        y_low = y_pos(low_price)
        y_open = y_pos(open_price)
        y_close = y_pos(close_price)
        body_y = min(y_open, y_close)
        body_h = max(1.2, abs(y_close - y_open))
        vol_top = vol_y(volume)
        vol_h = max(1.0, volume_bottom - vol_top)
        parts.append(f'<line x1="{x:.2f}" x2="{x:.2f}" y1="{y_high:.2f}" y2="{y_low:.2f}" stroke="{color}" stroke-width="{wick_w:.2f}"/>')
        parts.append(
            f'<rect x="{x - candle_w / 2:.2f}" y="{body_y:.2f}" width="{candle_w:.2f}" height="{body_h:.2f}" '
            f'rx="1.2" fill="{color}" opacity="0.96"/>'
        )
        parts.append(
            f'<rect x="{x - candle_w / 2:.2f}" y="{vol_top:.2f}" width="{candle_w:.2f}" height="{vol_h:.2f}" '
            f'rx="1" fill="{color}" opacity="0.55"/>'
        )

    parts.append("</svg>")
    return "".join(parts)


INDEX_TICKERS = (
    ("SPY", "S&P 500"),
    ("QQQ", "Nasdaq 100"),
    ("IWM", "Small caps"),
)


@st.cache_data(ttl=ALPACA_CACHE_TTL_SEC, show_spinner=False)
def fetch_index_bars(data_source: str, alpaca_realtime: bool = True) -> dict[str, pd.DataFrame]:
    symbols = tuple(symbol for symbol, _ in INDEX_TICKERS)
    bars: dict[str, pd.DataFrame] = {}

    if data_source in {DATA_SOURCE_ALPACA_SIP, DATA_SOURCE_AUTO} and ALPACA_KEY and ALPACA_SECRET:
        bars.update(fetch_alpaca_sip_batch(symbols, 40, alpaca_realtime))

    missing = tuple(symbol for symbol in symbols if symbol not in bars)
    if data_source in {DATA_SOURCE_YAHOO, DATA_SOURCE_AUTO} and missing and yf is not None:
        bars.update(fetch_yahoo_batch(missing, 40))

    return bars


def render_market_overview(data_source: str, alpaca_realtime: bool = True) -> None:
    bars = fetch_index_bars(data_source, alpaca_realtime)
    cards: list[str] = []
    for symbol, name in INDEX_TICKERS:
        df = bars.get(symbol)
        if df is None or len(df) < 2:
            cards.append(
                f'<div class="market-card"><div class="market-card-head">'
                f'<div><div class="market-symbol">{symbol}</div><div class="desk-muted">{html.escape(name)}</div></div>'
                f'<div class="market-change flat">нет данных</div></div></div>'
            )
            continue

        close = pd.to_numeric(df["Close"], errors="coerce").dropna()
        if len(close) < 2:
            cards.append(
                f'<div class="market-card"><div class="market-card-head">'
                f'<div><div class="market-symbol">{symbol}</div><div class="desk-muted">{html.escape(name)}</div></div>'
                f'<div class="market-change flat">нет данных</div></div></div>'
            )
            continue
        last = float(close.iloc[-1])
        prev = float(close.iloc[-2])
        change_pct = (last - prev) / prev * 100 if prev > 0 else 0.0
        tone = "up" if change_pct >= 0 else "down"
        chart_svg = pattern_chart_svg(pattern_chart_payload(df, 35, visible_candles=35, timeframe="D", show_default_band=False))
        cards.append(
            f'<div class="market-card"><div class="market-card-head">'
            f'<div><div class="market-symbol">{symbol}</div><div class="desk-muted">{html.escape(name)}</div></div>'
            f'<div class="market-change {tone}">{change_pct:+.2f}%<br><span>${last:,.2f}</span></div>'
            f'</div><div class="market-chart">{chart_svg}</div></div>'
        )

    if not cards:
        return

    st.markdown(
        '<div class="market-overview">'
        '<div class="market-title">Направление рынка сегодня</div>'
        f'<div class="market-grid">{"".join(cards)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def score_base_signal(setup: BaseImpulse, cfg: ScanConfig) -> int:
    volume_score = min(70.0, setup.volume_mult / max(cfg.base_volume_mult, 0.1) * 35.0)
    move_score = min(20.0, max(0.0, setup.move_pct) * 2.0)
    return int(round(volume_score + move_score + 10.0))


def score_rvol(setup: RvolSetup, cfg: ScanConfig) -> int:
    volume_score = min(60.0, setup.rvol / max(cfg.rvol_mult, 0.1) * 30.0)
    liquidity_score = min(25.0, setup.dollar_volume / 2_000_000 * 25.0)
    move_score = min(15.0, max(0.0, setup.move_pct) * 0.6)
    return int(round(volume_score + liquidity_score + move_score))


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


def score_momentum_pulse(setup: MomentumPulse, cfg: ScanConfig) -> int:
    volume_score = min(
        50.0,
        setup.rvol_5m / max(cfg.momentum_volume_mult, 0.1) * 30.0
        + setup.rvol_15m / max(cfg.momentum_confirm_volume_mult, 0.1) * 14.0
        + setup.volume_acceleration / max(cfg.momentum_min_volume_acceleration, 0.1) * 6.0,
    )
    move_score = min(
        12.0,
        abs(setup.move_5m_pct) / max(cfg.momentum_min_fast_move_pct, 0.1) * 5.0
        + abs(setup.move_15m_pct) / max(cfg.momentum_min_confirm_move_pct, 0.1) * 7.0,
    )
    liquidity_score = min(
        20.0,
        setup.dollar_5m / max(cfg.momentum_min_5m_dollar_volume, 1) * 7.0
        + setup.dollar_15m / max(cfg.momentum_min_15m_dollar_volume, 1) * 8.0
        + setup.dollar_day / max(cfg.momentum_min_day_dollar_volume, 1) * 5.0,
    )
    freshness_score = max(0.0, min(8.0, 8.0 - setup.bar_age_minutes / max(cfg.momentum_max_bar_age_minutes, 1) * 3.0))
    quality_score = 0.0
    if setup.vwap_aligned:
        quality_score += 4.0
    if setup.ema_aligned:
        quality_score += 4.0
    if setup.breakout_confirmed:
        quality_score += 4.0
    if setup.directional_bars_confirmed:
        quality_score += 3.0
    if setup.early_volume_wave:
        quality_score += 3.0
    if abs(setup.vwap_distance_pct) <= 6.0:
        quality_score += 1.0
    quality_score = min(15.0, quality_score)
    return int(round(max(0.0, min(100.0, volume_score + liquidity_score + move_score + freshness_score + quality_score))))


def detect_momentum_signal(
    ticker_info: dict[str, Any],
    df: pd.DataFrame,
    cfg: ScanConfig,
    reference_time: datetime,
) -> dict[str, Any] | None:
    setup = build_momentum_pulse(df, cfg, reference_time)
    if setup is None:
        return None

    price = setup.price
    if price < cfg.min_price or price > cfg.max_price:
        return None

    score = score_momentum_pulse(setup, cfg)
    if score < cfg.momentum_min_score:
        return None

    chart_df = momentum_intraday_frame(df, cfg, reference_time)
    direction_word = "ВВЕРХ" if setup.direction == MOMENTUM_DIR_UP else "ВНИЗ"
    direction_arrow = "↑" if setup.direction == MOMENTUM_DIR_UP else "↓"
    source = df.attrs.get("source", "")

    return {
        "_sig": SIG_MOMENTUM,
        "_rvol": setup.rvol_5m,
        "_score": score,
        "_width": abs(setup.move_15m_pct),
        "_gap": setup.vwap_distance_pct,
        "_move_pct": setup.move_5m_pct,
        "_momentum_direction": setup.direction,
        "_momentum_rvol_15m": setup.rvol_15m,
        "_momentum_move_15m": setup.move_15m_pct,
        "_momentum_bar_age": setup.bar_age_minutes,
        "_momentum_volume_acceleration": setup.volume_acceleration,
        "_momentum_prior_fast_rvol": setup.prior_fast_rvol,
        "_momentum_recent_prior_max_rvol": setup.recent_prior_max_rvol,
        "_momentum_fast_volume_share_pct": setup.fast_volume_share_pct,
        "_momentum_multi_minute_volume": setup.multi_minute_volume_confirmed,
        "_momentum_quality_checks": setup.quality_checks,
        "_chart_payload": pattern_chart_payload(
            chart_df,
            cfg.momentum_confirm_minutes,
            visible_candles=MINUTE_CHART_VISIBLE_CANDLES,
            band_days=0,
            timeframe="M",
            show_default_band=False,
        ),
        "_scanner": cfg.scanner_mode,
        "Тикер": ticker_info["ticker"],
        "Название": (ticker_info.get("name") or "")[:34],
        "Биржа": ticker_info.get("exchange", ""),
        "Сигнал": f"{SIGNAL_LABELS[SIG_MOMENTUM]} {direction_word}",
        "Цена": round(price, 4),
        "Выход %": f"{setup.move_5m_pct:+.1f}%",
        "Гэп сегодня": f"VWAP {setup.vwap_distance_pct:+.1f}%",
        "Объём ×": round(setup.rvol_5m, 2),
        "RVOL 15м": round(setup.rvol_15m, 2),
        "Объём": int(setup.volume_5m),
        "Объём 15м": int(setup.volume_15m),
        "Движение 15м": f"{setup.move_15m_pct:+.1f}%",
        "$ 5м": int(setup.dollar_5m),
        "$ 15м": int(setup.dollar_15m),
        "Долларовый объём": int(setup.dollar_5m),
        "Капитализация": ticker_info.get("market_cap") or 0,
        "Балл": score,
        "Источник": source,
        "Время": f"{now_et_str()} {direction_arrow}",
    }


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
        score = score_base_signal(base, cfg)
        signal = SIGNAL_LABELS[SIG_BASE]
        return {
            "_sig": SIG_BASE,
            "_rvol": base.volume_mult,
            "_score": score,
            "_width": base.width_pct,
            "_gap": latest_gap_pct,
            "_move_pct": base.move_pct,
            "_volume_over_max_pct": volume_over_max_pct,
            "_chart_payload": pattern_chart_payload(
                df,
                cfg.base_impulse_days,
                base.low,
                base.high,
                "база",
                visible_candles=CHART_VISIBLE_CANDLES,
                band_days=cfg.base_impulse_days,
                timeframe="D",
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

    if cfg.scanner_mode == SCANNER_RVOL:
        setup = build_rvol_setup(df, cfg)
        if setup is None:
            return None
        score = score_rvol(setup, cfg)
        return {
            "_sig": SIG_RVOL,
            "_rvol": setup.rvol,
            "_score": score,
            "_width": setup.width_pct,
            "_gap": latest_gap_pct,
            "_move_pct": setup.move_pct,
            "_chart_payload": pattern_chart_payload(
                df,
                setup.range_days,
                setup.low,
                setup.high,
                "RW-диапазон",
                visible_candles=CHART_VISIBLE_CANDLES,
                band_days=setup.range_days,
                timeframe="D",
            ),
            "_scanner": cfg.scanner_mode,
            "Тикер": ticker_info["ticker"],
            "Название": (ticker_info.get("name") or "")[:34],
            "Биржа": ticker_info.get("exchange", ""),
            "Сигнал": SIGNAL_LABELS[SIG_RVOL],
            "Цена": round(price, 4),
            "Выход %": f"{setup.move_pct:+.1f}%",
            "Гэп сегодня": f"{latest_gap_pct:+.1f}%",
            "Объём ×": round(setup.rvol, 2),
            "Объём": int(latest_volume),
            "Средний объём": int(setup.avg_volume),
            "Тело свечи %": round(body_pct, 1),
            "Долларовый объём": int(setup.dollar_volume),
            "Капитализация": ticker_info.get("market_cap") or 0,
            "Балл": score,
            "Источник": df.attrs.get("source", ""),
            "Время": now_et_str(),
        }

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
            "_chart_payload": pattern_chart_payload(
                df,
                cfg.vcp_days,
                setup.low,
                setup.high,
                "VCP-база",
                visible_candles=CHART_VISIBLE_CANDLES,
                band_days=min(cfg.vcp_days, CHART_VISIBLE_CANDLES),
                timeframe="D",
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
            "_chart_payload": pattern_chart_payload(
                df,
                max(cfg.spring_support_days, 30),
                setup.support * 0.99,
                setup.support * 1.01,
                "поддержка Spring",
                visible_candles=CHART_VISIBLE_CANDLES,
                band_days=min(max(cfg.spring_support_days, 30), CHART_VISIBLE_CANDLES),
                timeframe="D",
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
    alpaca_realtime: bool,
    progress_box: Any,
    status_box: Any,
    table_box: Any,
    send_alerts: bool,
) -> list[dict[str, Any]]:
    scan_started_at = now_et()
    dismissed = active_dismissed_tickers()
    if dismissed:
        ticker_infos = [
            item
            for item in ticker_infos
            if normalize_ticker_id(item.get("ticker")) not in dismissed
        ]

    hits: list[dict[str, Any]] = []
    total = len(ticker_infos)
    st.session_state.stats = {"checked": 0, "signals": 0}
    st.session_state.scan_errors = []

    if total <= 0:
        st.session_state.last_scan_elapsed = format_elapsed_since(scan_started_at)
        st.session_state.last_scan_seconds = elapsed_seconds_since(scan_started_at)
        status_box.caption(f"В этой пачке все тикеры скрыты на 7 часов.{elapsed_scan_suffix(scan_started_at)}")
        return []

    if cfg.scanner_mode == SCANNER_MOMENTUM:
        bars = load_momentum_bars(ticker_infos, cfg, data_source, alpaca_realtime, progress_box, status_box, scan_started_at)
    else:
        bars = load_bars(ticker_infos, cfg, data_source, alpaca_realtime, progress_box, status_box, scan_started_at)
    today = now_et().date()

    for idx, ticker_info in enumerate(ticker_infos, start=1):
        ticker = ticker_info["ticker"]
        progress_box.progress(min(1.0, 0.7 + 0.3 * idx / max(total, 1)))
        if idx % 50 == 1 or idx == total:
            status_box.caption(
                f"Анализирую {idx}/{total} · найдено: {len(hits)}"
                f"{elapsed_scan_suffix(scan_started_at)}"
            )

        try:
            history = bars.get(str(ticker).upper())
            if history is None:
                st.session_state.stats["checked"] = idx
                continue
            if cfg.scanner_mode == SCANNER_MOMENTUM:
                row = detect_momentum_signal(ticker_info, history, cfg, scan_started_at)
            else:
                row = detect_signal(ticker_info, history, cfg, today)
        except Exception as exc:
            LOGGER.exception("Scan failed for %s", ticker)
            remember_error(f"{ticker}: {exc}")
            row = None

        if row:
            hits.append(row)
            st.session_state.stats["signals"] = len(hits)
            visible_hits = sort_results(hits, cfg.base_impulse_only)
            visible_frame = display_frame(visible_hits, cfg.base_impulse_only)
            table_box.dataframe(
                styled_display_frame(visible_frame),
                use_container_width=True,
                hide_index=True,
                column_config=display_column_config(cfg.base_impulse_only),
            )
            if send_alerts:
                notify_signal(row)

        st.session_state.stats["checked"] = idx

    st.session_state.last_scan_elapsed = format_elapsed_since(scan_started_at)
    st.session_state.last_scan_seconds = elapsed_seconds_since(scan_started_at)
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
            LOGGER.warning("Telegram failed with status %s.", resp.status_code)
            return False
        return True
    except Exception as exc:
        LOGGER.warning("Telegram request failed: %s", exc)
        return False


def notification_key(row: dict[str, Any]) -> str:
    direction = row.get("_momentum_direction", "")
    return f"{now_et().date().isoformat()}:{row.get('_scanner', '')}:{row['Тикер']}:{row.get('_sig') or row.get('Сигнал', '')}:{direction}"


def notify_signal(row: dict[str, Any]) -> None:
    """Один Telegram-сигнал в день; помечаем только после успешной отправки."""
    notified = st.session_state.setdefault("notified_signals", set())
    key = notification_key(row)
    if key in notified:
        return
    if send_telegram(telegram_signal_message(row)):
        notified.add(key)


def telegram_signal_message(row: dict[str, Any]) -> str:
    ticker = re.sub(r"[^A-Z]", "", str(row["Тикер"]).upper()) or "TICKER"
    ticker = html.escape(ticker)
    rvol = safe_float(row.get("_rvol") or row.get("Объём ×"))
    move_pct = safe_float(row.get("_move_pct"))
    if rvol <= 0:
        return f"{ticker} 0.00x +0%"
    return f"{ticker} {rvol:.2f}x {move_pct:+.1f}%"


def result_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return str(row.get("_scanner", "")), str(row.get("Тикер", "")), str(row.get("Сигнал", ""))


def market_session_key(current: datetime | None = None) -> str:
    current = (current or now_et()).astimezone(MARKET_TZ)
    session_start = current.replace(hour=9, minute=30, second=0, microsecond=0)
    session_date = current.date() if current >= session_start else (current - timedelta(days=1)).date()
    return session_date.isoformat()


def current_session_seen_result_keys() -> set[tuple[str, str, str]]:
    session_key = market_session_key()
    if st.session_state.get("seen_signal_session_key") != session_key:
        st.session_state.seen_signal_session_key = session_key
        st.session_state.seen_signal_keys = set()
    seen = st.session_state.setdefault("seen_signal_keys", set())
    if not isinstance(seen, set):
        seen = set(seen or [])
        st.session_state.seen_signal_keys = seen
    return seen


def remember_seen_results(rows: list[dict[str, Any]]) -> None:
    session_key = market_session_key()
    seen = current_session_seen_result_keys()
    for row in rows:
        if isinstance(row, dict) and row.get("_seen_session_key") == session_key:
            seen.add(result_key(row))
    st.session_state.seen_signal_keys = seen


def clear_new_scan_flags(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleared: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            next_row = row.copy()
            next_row["_new_this_scan"] = False
            cleared.append(next_row)
    return cleared


def mark_new_scan_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    session_key = market_session_key()
    seen = current_session_seen_result_keys()
    marked: list[dict[str, Any]] = []
    scan_keys: set[tuple[str, str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = result_key(row)
        next_row = row.copy()
        next_row["_new_this_scan"] = key not in seen and key not in scan_keys
        next_row["_seen_session_key"] = session_key
        marked.append(next_row)
        scan_keys.add(key)
    seen.update(scan_keys)
    st.session_state.seen_signal_keys = seen
    return marked


def normalize_ticker_id(value: Any) -> str:
    return re.sub(r"[^A-Z0-9.\-]+", "", str(value or "").upper()).strip()


def parse_dismiss_expiry(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        expiry = value
    elif isinstance(value, str) and value.strip():
        try:
            expiry = datetime.fromisoformat(value.strip())
        except ValueError:
            return None
    else:
        return None
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=MARKET_TZ)
    return expiry.astimezone(MARKET_TZ)


def active_dismissed_tickers() -> dict[str, datetime]:
    raw = st.session_state.setdefault("dismissed_tickers", {})
    if not isinstance(raw, dict):
        raw = {}
    current = now_et()
    active: dict[str, datetime] = {}
    for ticker, expiry_raw in raw.items():
        symbol = normalize_ticker_id(ticker)
        expiry = parse_dismiss_expiry(expiry_raw)
        if symbol and expiry and expiry > current:
            active[symbol] = expiry
    st.session_state.dismissed_tickers = {ticker: expiry.isoformat() for ticker, expiry in active.items()}
    return active


def is_ticker_dismissed(ticker: Any) -> bool:
    symbol = normalize_ticker_id(ticker)
    return bool(symbol and symbol in active_dismissed_tickers())


def dismiss_ticker(ticker: Any) -> str:
    symbol = normalize_ticker_id(ticker)
    if not symbol:
        return ""
    dismissed = active_dismissed_tickers()
    dismissed[symbol] = now_et() + timedelta(hours=DISMISS_TTL_HOURS)
    st.session_state.dismissed_tickers = {key: value.isoformat() for key, value in dismissed.items()}
    st.session_state.last_dismissed_ticker = symbol
    return symbol


def filter_dismissed_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dismissed = active_dismissed_tickers()
    if not dismissed:
        return rows
    return [row for row in rows if normalize_ticker_id(row.get("Тикер")) not in dismissed]


def rerun_app() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


def sort_results(rows: list[dict[str, Any]], base_pattern: bool = False) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            safe_float(row.get("_rvol") or row.get("Объём ×")),
            safe_float(row.get("Объём")),
            safe_float(row.get("Долларовый объём")),
            abs(safe_float(row.get("_move_pct"))),
            safe_float(row.get("Балл")),
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
    if cfg.scanner_mode == SCANNER_RVOL:
        return signal_code == SIG_RVOL
    if cfg.scanner_mode == SCANNER_VCP:
        return signal_code == SIG_VCP
    if cfg.scanner_mode == SCANNER_SPRING:
        return signal_code == SIG_SPRING
    if cfg.scanner_mode == SCANNER_MOMENTUM:
        return signal_code == SIG_MOMENTUM
    return False


def result_matches_data_mode(row: dict[str, Any], data_source: str | None, alpaca_realtime: bool) -> bool:
    if data_source is None:
        return True
    source = str(row.get("Источник", ""))
    if source.startswith("Alpaca SIP"):
        return source.startswith(alpaca_mode_label(alpaca_realtime))
    if source == "Yahoo Finance":
        return data_source in {DATA_SOURCE_AUTO, DATA_SOURCE_YAHOO}
    return True


def filter_results_for_config(
    rows: list[dict[str, Any]],
    cfg: ScanConfig,
    data_source: str | None = None,
    alpaca_realtime: bool = True,
    hide_dismissed: bool = True,
) -> list[dict[str, Any]]:
    active_rows = [row for row in rows if isinstance(row, dict) and result_matches_active_patterns(row, cfg)]
    active_rows = [row for row in active_rows if result_matches_data_mode(row, data_source, alpaca_realtime)]
    return filter_dismissed_results(active_rows) if hide_dismissed else active_rows


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
    return f"{number:,}".replace(",", " ")


def format_dollar_cell(value: Any) -> str:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return ""
    if number <= 0:
        return ""
    return f"${number:,}".replace(",", " ")


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
    if sig == SIG_MOMENTUM:
        direction = str(row.get("_momentum_direction", ""))
        if direction == MOMENTUM_DIR_UP:
            return "Импульс ↑"
        if direction == MOMENTUM_DIR_DOWN:
            return "Импульс ↓"
        return "Импульс"
    if sig in SIGNAL_SHORT_LABELS:
        return SIGNAL_SHORT_LABELS[sig]
    raw = str(row.get("Сигнал", ""))
    replacements = {
        "ВЗРЫВ ОБЪЁМА ИЗ БАЗЫ": "Взрыв базы",
    }
    return replacements.get(raw, raw)


def display_column_config(base_pattern: bool = False) -> dict[str, Any]:
    return {
        "Тикер": st.column_config.TextColumn("Тикер", width="small"),
        "Сигнал": st.column_config.TextColumn("Сигнал", width="medium"),
        "Цена": st.column_config.NumberColumn("Цена", width="small", format="$%.4f"),
        "RVOL": st.column_config.NumberColumn(
            "RVOL",
            width="small",
            format="%.2fx",
            help="Объём / выбранная база сравнения. В RW это средний дневной объём; во Взрыве базы это максимум прошлых свечей; в Pulse это объём последних минут против внутридневной нормы.",
        ),
        "Движение %": st.column_config.NumberColumn("Движение %", width="small", format="%.1f%%"),
        "Объём": st.column_config.NumberColumn("Объём", width="medium"),
        "Долларовый объём": st.column_config.NumberColumn("Долларовый объём", width="medium"),
        "Капитализация": st.column_config.NumberColumn("Капитализация", width="medium"),
        "Время": st.column_config.TextColumn("Время", width="small"),
    }


def spaced_number(value: Any, prefix: str = "") -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if pd.isna(number):
        return ""
    if number <= 0:
        return "—" if prefix else ""
    return f"{prefix}{int(round(number)):,}".replace(",", " ")


def display_frame(rows: list[dict[str, Any]], base_pattern: bool = False, include_chart: bool = True) -> pd.DataFrame:
    display_cols = DISPLAY_COLS
    if not rows:
        columns = display_cols if include_chart else [col for col in display_cols if col != "График"]
        return pd.DataFrame(columns=columns)

    frame = pd.DataFrame(rows)
    if "Сигнал" in frame.columns:
        frame["Сигнал"] = frame.apply(format_signal_cell, axis=1)
    if "Цена" in frame.columns:
        frame["Цена"] = pd.to_numeric(frame["Цена"], errors="coerce")
    if "_rvol" in frame.columns:
        frame["RVOL"] = pd.to_numeric(frame["_rvol"], errors="coerce")
    elif "Объём ×" in frame.columns:
        frame["RVOL"] = pd.to_numeric(frame["Объём ×"], errors="coerce")
    if "_move_pct" in frame.columns:
        frame["Движение %"] = pd.to_numeric(frame["_move_pct"], errors="coerce")
    elif "Выход %" in frame.columns:
        frame["Движение %"] = pd.to_numeric(frame["Выход %"].astype(str).str.replace("%", "", regex=False), errors="coerce")
    if "Объём" in frame.columns:
        frame["Объём"] = pd.to_numeric(frame["Объём"], errors="coerce").astype("Int64")
    if "Долларовый объём" in frame.columns:
        frame["Долларовый объём"] = pd.to_numeric(frame["Долларовый объём"], errors="coerce").astype("Int64")
    if "Капитализация" in frame.columns:
        frame["Капитализация"] = pd.to_numeric(frame["Капитализация"], errors="coerce").astype("Int64")
    if not include_chart and "График" in display_cols:
        display_cols = [col for col in display_cols if col != "График"]

    columns = [col for col in display_cols if col in frame.columns]
    return frame[columns]


def styled_display_frame(frame: pd.DataFrame) -> pd.io.formats.style.Styler:
    formatters = {
        "Объём": lambda value: spaced_number(value),
        "Долларовый объём": lambda value: spaced_number(value, "$"),
        "Капитализация": lambda value: spaced_number(value, "$"),
    }
    active_formatters = {col: fmt for col, fmt in formatters.items() if col in frame.columns}
    return frame.style.format(active_formatters)


def ai_secret_ready(value: str | None) -> bool:
    return bool(value and str(value).strip() not in AI_PLACEHOLDER_SECRETS)


def ai_missing_secrets() -> list[str]:
    missing = []
    if not ai_secret_ready(AI_CLAUDE_KEY):
        missing.append("ANTHROPIC_API_KEY")
    if not ai_secret_ready(AI_GROK_KEY):
        missing.append("XAI_API_KEY")
    return missing


def ai_tickers_from_results(rows: list[dict[str, Any]]) -> list[str]:
    tickers: list[str] = []
    seen: set[str] = set()
    for row in rows:
        ticker = re.sub(r"[^A-Z.]", "", str(row.get("Тикер", "")).upper())
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        tickers.append(ticker)
    return tickers


def ai_limit_options(total: int) -> list[int]:
    base = [5, 10, 15, 20]
    options = [value for value in base if value < total]
    if total > 0:
        options.append(total)
    return options or [0]


def ai_result_signature(tickers: list[str], cfg: ScanConfig, web_search: bool) -> str:
    return "|".join(
        [
            cfg.scanner_mode,
            ",".join(tickers),
            AI_CLAUDE_MODEL_SETTING,
            AI_GROK_MODEL_SETTING,
            "web" if web_search else "no_web",
        ]
    )


def ai_auto_model_requested(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"", "auto", "latest", "auto-latest", "best"}


def ai_model_version_tuple(model_id: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", model_id)[:6])


def ai_claude_family_score(model_id: str) -> int:
    lowered = model_id.lower()
    for index, family in enumerate(AI_CLAUDE_FAMILY_PRIORITY):
        if family and family in lowered:
            return len(AI_CLAUDE_FAMILY_PRIORITY) - index
    return 0


def ai_claude_model_score(model: dict[str, Any]) -> tuple[int, tuple[int, ...], str, str]:
    model_id = str(model.get("id") or "")
    created_at = str(model.get("created_at") or model.get("created") or "")
    return (
        ai_claude_family_score(model_id),
        ai_model_version_tuple(model_id),
        created_at,
        model_id,
    )


def ai_fetch_claude_models() -> list[dict[str, Any]]:
    if not ai_secret_ready(AI_CLAUDE_KEY):
        return []
    response = requests.get(
        "https://api.anthropic.com/v1/models",
        headers={
            "x-api-key": AI_CLAUDE_KEY,
            "anthropic-version": "2023-06-01",
        },
        params={"limit": 100},
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data", [])
    return data if isinstance(data, list) else []


def ai_pick_claude_model(models: list[dict[str, Any]]) -> str:
    candidates: list[dict[str, Any]] = []
    for model in models:
        model_id = str(model.get("id") or "")
        if not model_id.startswith("claude-"):
            continue
        if "mythos" in model_id.lower() and not AI_ALLOW_LIMITED_CLAUDE_MODELS:
            continue
        candidates.append(model)
    if not candidates:
        return AI_CLAUDE_FALLBACK_MODEL
    return str(max(candidates, key=ai_claude_model_score).get("id") or AI_CLAUDE_FALLBACK_MODEL)


def ai_resolve_claude_model() -> tuple[str, str]:
    setting = str(AI_CLAUDE_MODEL_SETTING or "").strip()
    if not ai_auto_model_requested(setting):
        return setting, "manual"
    try:
        model = ai_pick_claude_model(ai_fetch_claude_models())
        return model, "auto"
    except Exception as exc:
        LOGGER.warning("Claude model auto-selection failed: %s", exc)
        return AI_CLAUDE_FALLBACK_MODEL, "fallback"


def ai_grok_model_score(model_id: str) -> tuple[int, tuple[int, ...], str]:
    lowered = model_id.lower()
    if not lowered.startswith("grok-"):
        return (-1, (), model_id)
    if any(word in lowered for word in ("build", "image", "imagine", "voice", "audio", "tts", "stt")):
        return (0, ai_model_version_tuple(model_id), model_id)
    return (1, ai_model_version_tuple(model_id), model_id)


def ai_fetch_grok_models() -> list[str]:
    if not ai_secret_ready(AI_GROK_KEY):
        return []
    client = ai_make_grok_client()
    response = client.models.list()
    model_ids: list[str] = []
    for model in getattr(response, "data", []) or []:
        model_id = getattr(model, "id", None)
        if model_id:
            model_ids.append(str(model_id))
    return model_ids


def ai_resolve_grok_model() -> tuple[str, str]:
    setting = str(AI_GROK_MODEL_SETTING or "").strip()
    if not ai_auto_model_requested(setting):
        return setting, "manual"
    try:
        candidates = [
            model_id
            for model_id in ai_fetch_grok_models()
            if ai_grok_model_score(model_id)[0] > 0
        ]
        if candidates:
            return max(candidates, key=ai_grok_model_score), "auto"
    except Exception as exc:
        LOGGER.warning("Grok model auto-selection failed: %s", exc)
    return AI_GROK_FALLBACK_MODEL, "fallback"



def ai_resolved_items_for_tickers(tickers: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "input": ticker,
            "ticker": ticker,
            "company": None,
            "exchange": "unknown",
            "status": "public_stock",
            "confidence": "high",
            "note": "ticker from screener result",
        }
        for ticker in tickers
    ]


def ai_ticker_prompt(base_prompt: str, raw_tickers: str, resolved_items: list[dict[str, Any]]) -> str:
    public_tickers = [
        str(item["ticker"]).upper()
        for item in resolved_items
        if item.get("ticker") and item.get("status") in {"public_stock", "ambiguous"}
    ]
    resolution_lines = []
    for item in resolved_items:
        ticker = item.get("ticker") or "нет публичного тикера"
        company = item.get("company") or "не уточнено"
        status = item.get("status") or "unknown"
        confidence = item.get("confidence") or "low"
        note = item.get("note") or ""
        resolution_lines.append(
            f'- "{item.get("input")}" -> {ticker} | {company} | {status} | {confidence} | {note}'
        )

    ticker_list = ", ".join(public_tickers) if public_tickers else raw_tickers
    return f"""
Источник данных: торговый Streamlit-скринер. Это уже очищенный список найденных тикеров.

Сопоставление:
{chr(10).join(resolution_lines)}

Публичные тикеры для анализа: {ticker_list}

Жёсткое правило:
- анализируй только тикеры из строки "Публичные тикеры для анализа";
- не заменяй тикер похожей компанией;
- не добавляй другие тикеры;
- если по точному тикеру нет данных или новости, напиши "нет подтверждённой новости";
- итог по каждому тикеру должен относиться именно к этому тикеру.

Не анализируй слова из интерфейса, названия колонок, числа, проценты или случайные
фрагменты текста. Если по тикеру нет подтверждённой новости или данных, не выдумывай.

{base_prompt}
"""


def ai_claude_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def ai_grok_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text).strip()

    parts: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                parts.append(text)
            elif isinstance(content, dict) and content.get("text"):
                parts.append(str(content["text"]))
    return "\n".join(parts).strip()


def ai_grok_tools(web_search: bool) -> list[dict[str, Any]]:
    return [{"type": "web_search"}] if web_search else []


def ai_call_claude_with_tickers(raw_tickers: str, resolved_items: list[dict[str, Any]], model: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=AI_CLAUDE_KEY)
    response = client.messages.create(
        model=model,
        max_tokens=AI_CLAUDE_MAX_TOKENS,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ai_ticker_prompt(AI_CLAUDE_PROMPT, raw_tickers, resolved_items)}
                ],
            }
        ],
    )
    return ai_claude_text(response)


def ai_make_grok_client() -> Any:
    import httpx
    from openai import OpenAI

    return OpenAI(
        api_key=AI_GROK_KEY,
        base_url="https://api.x.ai/v1",
        timeout=httpx.Timeout(3600.0),
    )


def ai_call_grok_with_tickers(
    raw_tickers: str,
    resolved_items: list[dict[str, Any]],
    web_search: bool,
    model: str,
) -> str:
    client = ai_make_grok_client()
    request: dict[str, Any] = {
        "model": model,
        "max_output_tokens": AI_GROK_MAX_TOKENS,
        "store": False,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": ai_ticker_prompt(AI_GROK_SENTIMENT_PROMPT, raw_tickers, resolved_items)}
                ],
            }
        ],
    }
    tools = ai_grok_tools(web_search)
    if tools:
        request["tools"] = tools
    response = client.responses.create(**request)
    return ai_grok_text(response)


def ai_call_grok_synthesis(
    claude_answer: str,
    grok_answer: str,
    web_search: bool,
    model: str,
    tickers: list[str],
) -> str:
    client = ai_make_grok_client()
    prompt = AI_FINAL_SYNTHESIS_PROMPT_TEMPLATE.format(
        ticker_list=", ".join(tickers),
        claude_answer=claude_answer.strip(),
        grok_answer=grok_answer.strip(),
    )
    request: dict[str, Any] = {
        "model": model,
        "max_output_tokens": AI_SYNTHESIS_MAX_TOKENS,
        "store": False,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            }
        ],
    }
    tools = ai_grok_tools(web_search)
    if tools:
        request["tools"] = tools
    response = client.responses.create(**request)
    return ai_grok_text(response)


def ai_run_analysis_from_tickers(tickers: list[str], web_search: bool) -> dict[str, Any]:
    raw_tickers = " ".join(tickers)
    resolved_items = ai_resolved_items_for_tickers(tickers)
    claude_model, claude_model_source = ai_resolve_claude_model()
    grok_model, grok_model_source = ai_resolve_grok_model()
    claude_answer = ai_call_claude_with_tickers(raw_tickers, resolved_items, claude_model)
    try:
        grok_answer = ai_call_grok_with_tickers(raw_tickers, resolved_items, web_search, grok_model)
        final_answer = ai_call_grok_synthesis(claude_answer, grok_answer, web_search, grok_model, tickers)
    except Exception as exc:
        if grok_model == AI_GROK_FALLBACK_MODEL:
            raise
        LOGGER.warning("Grok model %s failed, retrying %s: %s", grok_model, AI_GROK_FALLBACK_MODEL, exc)
        grok_model = AI_GROK_FALLBACK_MODEL
        grok_model_source = "fallback"
        grok_answer = ai_call_grok_with_tickers(raw_tickers, resolved_items, web_search, grok_model)
        final_answer = ai_call_grok_synthesis(claude_answer, grok_answer, web_search, grok_model, tickers)
    return {
        "tickers": tickers,
        "claude": claude_answer,
        "grok": grok_answer,
        "final": final_answer,
        "created_at": now_et_str(),
        "web_search": web_search,
        "claude_model": claude_model,
        "claude_model_source": claude_model_source,
        "grok_model": grok_model,
        "grok_model_source": grok_model_source,
    }


def ai_field_value(block: str, label: str) -> str:
    pattern = rf"^{re.escape(label)}:\s*(.+)$"
    match = re.search(pattern, block, flags=re.MULTILINE)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


def ai_parse_final_rows(final_text: str) -> list[dict[str, str]]:
    blocks = re.split(r"\n\s*---+\s*\n", final_text.strip())
    rows: list[dict[str, str]] = []
    for block in blocks:
        ticker = ai_field_value(block, "Тикер")
        if not ticker:
            continue
        rows.append(
            {
                "Тикер": ticker.upper(),
                "Новость": ai_field_value(block, "Главная причина / новость (с датой)"),
                "Сила": ai_field_value(block, "Сила катализатора"),
                "Сторона": (
                    ai_field_value(block, "Сторона")
                    or ai_field_value(block, "Направление")
                    or ai_field_value(block, "Сделка")
                ),
                "Вход": (
                    ai_field_value(block, "Вход сейчас")
                    or ai_field_value(block, "Решение")
                    or ai_field_value(block, "Вход/overnight")
                ),
                "Overnight": (
                    ai_field_value(block, "Overnight")
                    or ai_field_value(block, "Овернайт")
                ),
                "Риски": ai_field_value(block, "Главные риски"),
                "Вердикт": ai_field_value(block, "Короткий вердикт"),
            }
        )
    return rows


def ai_filter_rows_to_requested_tickers(rows: list[dict[str, str]], tickers: list[str]) -> list[dict[str, str]]:
    allowed = {normalize_ticker_id(ticker) for ticker in tickers}
    if not allowed:
        return rows
    filtered: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        ticker = normalize_ticker_id(row.get("Тикер"))
        if ticker and ticker in allowed and ticker not in seen:
            filtered.append(row)
            seen.add(ticker)
    return filtered


def ai_overnight_class(value: str) -> tuple[str, str]:
    normalized = value.strip().upper()
    if "НЕТ" in normalized or normalized == "NO":
        return "ai-no", "Нет"
    if "ОСТОРОЖ" in normalized or "CAUTION" in normalized:
        return "ai-careful", "Осторожно"
    if "ВХОД" in normalized or "ДА" in normalized or normalized == "YES":
        return "ai-yes", "Вход"
    return "ai-neutral", value or "Неясно"


def render_ai_ticker_cards(rows: list[dict[str, str]]) -> None:
    for index, row in enumerate(rows, start=1):
        badge_class, badge_text = ai_overnight_class(row["Вход"])
        st.markdown(
            f"""
            <div class="ai-ticker-card {badge_class}">
                <div class="ai-ticker-head">
                    <div>
                        <div class="ai-ticker-symbol">#{index} {html.escape(row["Тикер"])}</div>
                        <div class="ai-ticker-news">{html.escape(row["Новость"] or "Новость не подтверждена")}</div>
                    </div>
                    <div class="ai-badge {badge_class}">{html.escape(badge_text)}</div>
                </div>
                <div class="ai-ticker-grid">
                    <div><span>Сторона</span><strong>{html.escape(row["Сторона"] or "неясно")}</strong></div>
                    <div><span>Вход</span><strong>{html.escape(row["Вход"] or "неясно")}</strong></div>
                    <div><span>Overnight</span><strong>{html.escape(row["Overnight"] or "неясно")}</strong></div>
                    <div><span>Катализатор</span><strong>{html.escape(row["Сила"] or "неясно")}</strong></div>
                </div>
                <div class="ai-verdict"><strong>Риск:</strong> {html.escape(row["Риски"] or "нет данных")}</div>
                <div class="ai-verdict">{html.escape(row["Вердикт"] or "Нет короткого вердикта.")}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_ai_analysis_result(result: dict[str, Any]) -> None:
    final_text = str(result.get("final") or "")
    rows = ai_filter_rows_to_requested_tickers(
        ai_parse_final_rows(final_text),
        [str(ticker) for ticker in result.get("tickers", [])],
    )
    if rows:
        render_ai_ticker_cards(rows)
        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Тикер": st.column_config.TextColumn("Тикер", width="small"),
                "Сторона": st.column_config.TextColumn("Сторона", width="small"),
                "Сила": st.column_config.TextColumn("Сила", width="small"),
                "Вход": st.column_config.TextColumn("Вход", width="small"),
                "Overnight": st.column_config.TextColumn("Overnight", width="small"),
                "Новость": st.column_config.TextColumn("Новость", width="large"),
                "Риски": st.column_config.TextColumn("Риски", width="medium"),
                "Вердикт": st.column_config.TextColumn("Вердикт", width="large"),
            },
        )
    else:
        st.markdown(final_text)

    report_text = f"""# AI-разбор найденных тикеров

Создано: {result.get("created_at", "")}
Тикеры: {", ".join(result.get("tickers", []))}
Claude model: {result.get("claude_model", AI_CLAUDE_MODEL_SETTING)} ({result.get("claude_model_source", "setting")})
Grok model: {result.get("grok_model", AI_GROK_MODEL_SETTING)} ({result.get("grok_model_source", "setting")})
Grok поиск новостей: {"on" if result.get("web_search") else "off"}

## Итог

{final_text}
"""
    st.download_button(
        "Скачать AI-разбор",
        data=report_text.encode("utf-8"),
        file_name=f"ai_stock_analysis_{now_et().strftime('%Y%m%d_%H%M')}.md",
        mime="text/markdown",
        use_container_width=True,
    )


def render_ai_analysis_panel(rows: list[dict[str, Any]], cfg: ScanConfig) -> None:
    tickers_all = ai_tickers_from_results(rows)
    if not tickers_all:
        return

    st.markdown(
        f"""
        <div class="ai-analysis-panel">
            <div class="ai-analysis-head">
                <div>
                    <div class="ai-analysis-title">AI-разбор Claude + Grok</div>
                    <div class="ai-analysis-subtitle">
                        Сверху вниз: лучшие идеи Long/Short по новости, моментуму и шансам на вход/overnight.
                        Claude отсекает фундаментальные красные флаги.
                    </div>
                </div>
                <div class="base-results-stats">
                    {chip("Доступно", len(tickers_all), "blue")}
                    {chip("Источник", SCANNER_LABELS.get(cfg.scanner_mode, "Скринер"))}
                    {chip("Claude", AI_CLAUDE_MODEL_SETTING)}
                    {chip("Grok", AI_GROK_MODEL_SETTING)}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    limit_options = ai_limit_options(len(tickers_all))
    default_limit = min(AI_DEFAULT_TICKER_LIMIT, len(tickers_all))
    default_index = limit_options.index(default_limit) if default_limit in limit_options else 0
    ctrl_col, web_col = st.columns([0.58, 0.42])
    with ctrl_col:
        ticker_limit = st.selectbox(
            "Сколько тикеров разобрать",
            options=limit_options,
            index=default_index,
            format_func=lambda value: f"Все ({value})" if value == len(tickers_all) else f"Топ-{value}",
            key=f"ai_ticker_limit_{cfg.scanner_mode}",
        )
    with web_col:
        web_search = st.toggle(
            "Grok ищет новости",
            value=AI_GROK_WEB_SEARCH_DEFAULT,
            key=f"ai_web_search_{cfg.scanner_mode}",
            help="Grok будет искать свежие новости и катализаторы. Это полезнее, но дороже и дольше.",
        )

    selected_tickers = tickers_all[: int(ticker_limit)]
    st.caption(f"В AI-разбор уйдут: {', '.join(selected_tickers)}")

    missing = ai_missing_secrets()
    if missing:
        st.warning(
            "AI-разбор пока не включится: добавь в Streamlit Secrets "
            + ", ".join(missing)
            + ". В коде ключей нет и не должно быть."
        )

    analyze_clicked = st.button(
        "Разобрать найденные тикеры Claude + Grok",
        type="primary",
        use_container_width=True,
        disabled=bool(missing),
    )
    signature = ai_result_signature(selected_tickers, cfg, web_search)
    if analyze_clicked:
        try:
            with st.spinner("AI-разбор: Claude проверяет риски, Grok ищет новости..."):
                result = ai_run_analysis_from_tickers(selected_tickers, web_search)
            result["signature"] = signature
            st.session_state.ai_analysis_result = result
            st.session_state.ai_analysis_error = ""
            st.success("AI-разбор готов.")
        except Exception as exc:
            st.session_state.ai_analysis_error = str(exc)
            st.error(f"AI-разбор не выполнен: {exc}")

    error_text = str(st.session_state.get("ai_analysis_error") or "")
    if error_text:
        with st.expander("Ошибка AI-разбора"):
            st.write(error_text)

    result = st.session_state.get("ai_analysis_result")
    if isinstance(result, dict) and result.get("final"):
        if result.get("signature") != signature:
            st.caption("Показан последний AI-разбор. Если список тикеров изменился, нажми кнопку заново.")
        render_ai_analysis_result(result)


def render_results_summary(rows: list[dict[str, Any]]) -> None:
    count = len(rows)
    best_rvol = max((safe_float(row.get("_rvol")) for row in rows), default=0.0)
    total_dollar_volume = sum(safe_float(row.get("Долларовый объём")) for row in rows)
    latest_time = str(rows[0].get("Время", now_et_str())) if rows else now_et_str()
    count_parts = []
    for code in (SIG_BASE, SIG_RVOL, SIG_VCP, SIG_SPRING, SIG_MOMENTUM):
        signal_count = sum(1 for row in rows if str(row.get("_sig", "")) == code)
        if signal_count:
            count_parts.append(f"{SIGNAL_SHORT_LABELS.get(code, code)} {signal_count}")
    signal_mix = " · ".join(count_parts) if count_parts else "нет"
    st.markdown(
        f"""
        <div class="base-results-bar">
            <div>
                <div class="base-results-title">Найденные акции</div>
                <div class="base-results-subtitle">По умолчанию сверху акции с самым большим RVOL.</div>
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


def render_results_table(rows: list[dict[str, Any]], cfg: ScanConfig) -> None:
    results_frame = display_frame(rows, cfg.base_impulse_only)
    if results_frame.empty:
        return

    st.dataframe(
        styled_display_frame(results_frame),
        use_container_width=True,
        hide_index=True,
        column_config=display_column_config(cfg.base_impulse_only),
        height=420,
    )


def render_signal_gallery(rows: list[dict[str, Any]], alpaca_realtime: bool = True) -> None:
    cards = sort_results([
        row
        for row in rows
        if isinstance(row, dict) and row.get("_chart_payload")
    ])
    if not cards:
        return

    st.markdown(
        f'<div class="desk-section-title">Графики найденных акций · {len(cards)}</div>',
        unsafe_allow_html=True,
    )

    minute_bars: dict[str, pd.DataFrame] = {}
    minute_symbols = list(
        dict.fromkeys(
            str(row.get("Тикер", "")).upper().strip()
            for row in cards
            if row.get("Тикер") and row.get("_scanner") != SCANNER_MOMENTUM
        )
    )
    for batch in chunks(minute_symbols, 25):
        minute_bars.update(fetch_alpaca_minute_bars_batch(tuple(batch), MINUTE_CHART_VISIBLE_CANDLES, alpaca_realtime))

    used_card_keys: set[str] = set()
    for row in cards:
        ticker_raw = str(row.get("Тикер", ""))
        ticker_key = ticker_raw.upper().strip()
        signal_raw = str(row.get("_sig", ""))
        scanner_raw = str(row.get("_scanner", ""))
        is_momentum = scanner_raw == SCANNER_MOMENTUM
        direction_raw = str(row.get("_momentum_direction", ""))
        key_seed = f"{scanner_raw}_{ticker_key}_{signal_raw}_{direction_raw}"
        key_base_root = re.sub(r"[^A-Za-z0-9_]+", "_", key_seed).strip("_") or "signal_card"
        key_base = key_base_root
        duplicate_idx = 2
        while key_base in used_card_keys:
            key_base = f"{key_base_root}_{duplicate_idx}"
            duplicate_idx += 1
        used_card_keys.add(key_base)
        daily_payload = row.get("_chart_payload") or {}
        daily_svg = pattern_chart_svg(daily_payload)
        if not daily_svg:
            continue
        ticker = html.escape(str(row.get("Тикер", "")))
        if is_momentum:
            signal_text = "Импульс ↑" if row.get("_momentum_direction") == MOMENTUM_DIR_UP else "Импульс ↓"
        else:
            signal_text = SIGNAL_SHORT_LABELS.get(str(row.get("_sig", "")), str(row.get("Сигнал", "")))
        signal = html.escape(signal_text)
        price = html.escape(format_price_cell(row.get("Цена")))
        rw = html.escape(format_rw_cell(row.get("_rvol")))
        move = html.escape(format_percent_cell(row.get("_move_pct")))
        volume = html.escape(format_int_cell(row.get("Объём")))
        dollar_volume = html.escape(format_dollar_cell(row.get("Долларовый объём")))
        market_cap = html.escape(format_market_cap_cell(row.get("Капитализация")))
        card_state_class = " pattern-card-new" if row.get("_new_this_scan") else ""

        with st.container(key=f"chart_card_{key_base}"):
            info_col, action_col = st.columns([0.86, 0.14], vertical_alignment="top")
            with info_col:
                st.markdown(
                    f"""
                    <div class="pattern-chart-shell{card_state_class}">
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
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with action_col:
                st.button(
                    "×",
                    key=f"dismiss_chart_{key_base}",
                    help=f"Скрыть {ticker_raw} на {DISMISS_TTL_HOURS} часов",
                    on_click=dismiss_ticker,
                    args=(ticker_raw,),
                    use_container_width=True,
                )

            minute_block = ""
            if not is_momentum:
                minute_svg = ""
                minute_df = minute_bars.get(ticker_key)
                if minute_df is not None:
                    minute_svg = pattern_chart_svg(
                        pattern_chart_payload(
                            minute_df,
                            MINUTE_CHART_VISIBLE_CANDLES,
                            visible_candles=MINUTE_CHART_VISIBLE_CANDLES,
                            timeframe="M",
                            band_days=0,
                            show_default_band=False,
                        )
                    )

                minute_block = (
                    f'<div class="pattern-chart-panel"><div class="pattern-chart-panel-title">Минутка · {MINUTE_CHART_VISIBLE_CANDLES} баров</div>'
                    f'<div class="pattern-chart-svg">{minute_svg}</div></div>'
                    if minute_svg
                    else '<div class="pattern-chart-panel"><div class="desk-muted">Минутные свечи Alpaca сейчас недоступны.</div></div>'
                )
            chart_title = (
                f"Pulse 1Min · до {MINUTE_CHART_VISIBLE_CANDLES} баров"
                if is_momentum
                else f"Дневка · {CHART_VISIBLE_CANDLES} баров"
            )
            if daily_svg:
                extra_panel = minute_block if minute_block else ""
                st.markdown(
                    f"""
                    <div class="pattern-chart-stack">
                        <div class="pattern-chart-panel">
                            <div class="pattern-chart-panel-title">{html.escape(chart_title)}</div>
                            <div class="pattern-chart-svg">{daily_svg}</div>
                        </div>
                        {extra_panel}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


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
if "dismissed_tickers" not in st.session_state:
    st.session_state.dismissed_tickers = {}
if "last_dismissed_ticker" not in st.session_state:
    st.session_state.last_dismissed_ticker = ""
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
if "auto_scan_running" not in st.session_state:
    st.session_state.auto_scan_running = False
if "auto_scan_started_at" not in st.session_state:
    st.session_state.auto_scan_started_at = None
elif isinstance(st.session_state.auto_scan_started_at, datetime) and st.session_state.auto_scan_started_at.tzinfo is None:
    st.session_state.auto_scan_started_at = st.session_state.auto_scan_started_at.replace(tzinfo=MARKET_TZ)
if "last_scan_elapsed" not in st.session_state:
    st.session_state.last_scan_elapsed = ""
if "last_scan_seconds" not in st.session_state:
    st.session_state.last_scan_seconds = 0
if "ai_analysis_result" not in st.session_state:
    st.session_state.ai_analysis_result = {}
if "ai_analysis_error" not in st.session_state:
    st.session_state.ai_analysis_error = ""

auto_started_at = st.session_state.get("auto_scan_started_at")
if st.session_state.get("auto_scan_running") and isinstance(auto_started_at, datetime):
    auto_age = (now_et() - auto_started_at.astimezone(MARKET_TZ)).total_seconds()
    if auto_age > AUTO_SCAN_STALE_RUNNING_MINUTES * 60:
        st.session_state.auto_scan_running = False
        st.session_state.auto_scan_started_at = None


# ── SIDEBAR ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand-title">PR Screener</div>
            <div class="sidebar-brand-subtitle">Взрыв базы · RW · VCP · Spring · Pulse</div>
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
    rvol_active = scanner_mode == SCANNER_RVOL
    vcp_active = scanner_mode == SCANNER_VCP
    spring_active = scanner_mode == SCANNER_SPRING
    momentum_active = scanner_mode == SCANNER_MOMENTUM
    st.caption(SCANNER_HELP[scanner_mode])

    st.markdown('<div class="desk-section-title">Данные</div>', unsafe_allow_html=True)
    data_source_label = st.selectbox(
        "Свечи и дневной объём",
        [
            DATA_SOURCE_LABELS[DATA_SOURCE_ALPACA_SIP],
            DATA_SOURCE_LABELS[DATA_SOURCE_AUTO],
        ],
        index=0,
        help=(
            "По умолчанию используем Alpaca SIP. Резерв Yahoo можно включить вручную, "
            "если Alpaca временно не отдаёт часть тикеров."
        ),
    )
    data_source = {label: code for code, label in DATA_SOURCE_LABELS.items()}[data_source_label]
    alpaca_realtime = True
    if data_source in {DATA_SOURCE_AUTO, DATA_SOURCE_ALPACA_SIP}:
        alpaca_mode_choice = st.radio(
            "Режим Alpaca",
            ["Real-time", f"{ALPACA_SIP_DELAY_MINUTES} мин задержка"],
            index=0,
            horizontal=True,
            help=(
                "Real-time: новый режим, end=текущее время, нужен Algo Trader Plus/SIP real-time. "
                f"{ALPACA_SIP_DELAY_MINUTES} мин задержка: старая резервная версия, если подписка или доступ слетит."
            ),
        )
        alpaca_realtime = alpaca_mode_choice == "Real-time"
        st.caption(
            "Alpaca SIP: "
            + (
                "новая версия real-time без искусственной задержки."
                if alpaca_realtime
                else f"старая резервная версия с задержкой {ALPACA_SIP_DELAY_MINUTES} минут."
            )
        )
        if not (ALPACA_KEY and ALPACA_SECRET):
            st.warning("Для Alpaca SIP нужны ALPACA_KEY и ALPACA_SECRET в secrets.")
    if momentum_active:
        st.caption("Pulse использует только Alpaca SIP 1Min. Yahoo в этом режиме не нужен.")
    if data_source == DATA_SOURCE_AUTO and yf is None:
        st.warning("yfinance не установлен: Yahoo Finance недоступен как резерв.")

    st.markdown('<div class="desk-section-title">Рынок</div>', unsafe_allow_html=True)
    exchange = st.selectbox("Биржа", ["ALL", "NASDAQ", "NYSE", "AMEX"], index=0)
    max_scan_price = st.number_input(
        "Макс. цена для списка рынка",
        min_value=0.1,
        max_value=500.0,
        value=50.0 if momentum_active else 20.0,
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
            f"Авто-скан будет идти по всему списку до {format_int_cell(AUTO_SCAN_MARKET_LIMIT)} акций такими пачками."
        ),
    )
    st.caption("NASDAQ/NYSE/AMEX · обычные акции до 5 букв · без ETF, фондов, юнитов, варрантов, прав, привилегированных акций и долговых нот")

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
        disabled=base_impulse_only or momentum_active,
        help="Для RW, VCP и Spring фильтрует слишком тонкие акции. Для Взрыва из базы выключено, чтобы старый режим работал как раньше. Для Pulse есть отдельные 5м/15м фильтры.",
    )
    min_dollar_volume = 0 if base_impulse_only or momentum_active else int(min_dollar_volume_input)

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
    base_width_filter_enabled = st.toggle(
        "Учитывать ширину базы",
        value=True,
        disabled=not base_impulse_only,
        help=(
            "По умолчанию включено: ищем именно накопление в узкой базе. "
            "Если выключить, скринер не будет отсеивать широкие базы, но оставит остальные условия: "
            "открытие внутри вчерашней свечи и объём выше максимума прошлых свечей."
        ),
    )
    base_max_width_pct = st.slider(
        "Макс. ширина базы (%)",
        2.0,
        80.0,
        40.0,
        1.0,
        disabled=not base_impulse_only or not base_width_filter_enabled,
        help="Ширина канала считается по выбранным предыдущим свечам: high базы против low базы. 40% значит, что база за выбранные дни должна быть не шире 40%.",
    )
    base_volume_mult = st.slider(
        "Сегодняшний объём выше каждой прошлой свечи ×",
        1,
        50,
        2,
        1,
        disabled=not base_impulse_only,
        help="1 означает: сегодняшний объём строго больше максимального объёма среди предыдущих свечей. 50 означает: больше максимума предыдущих свечей в 50 раз.",
    )

    st.markdown('<div class="desk-section-title">Относительный объём RW</div>', unsafe_allow_html=True)
    rvol_avg_days = st.slider(
        "RW · средний объём за дней",
        5,
        60,
        30,
        1,
        disabled=not rvol_active,
        help="Сколько предыдущих дневных свечей берём для средней. Базовый рыночный пресет: 30 дней, чтобы сравнивать с месячной нормой.",
    )
    rvol_mult = st.slider(
        "RW · объём сегодня выше средней ×",
        1.5,
        20.0,
        2.0,
        0.5,
        disabled=not rvol_active,
        help="Сигнал появляется, когда сегодняшний объём минимум во столько раз выше средней за выбранные дни. Базовый пресет: 2x как заметное отклонение от обычного объёма.",
    )

    st.markdown('<div class="desk-section-title">VCP-сжатие</div>', unsafe_allow_html=True)
    vcp_days = st.slider(
        "Период VCP, дней",
        30,
        90,
        60,
        5,
        disabled=not vcp_active,
        help=SCANNER_HELP[SCANNER_VCP],
    )
    vcp_max_base_width_pct = st.slider("Макс. ширина всей базы (%)", 15.0, 70.0, 30.0, 1.0, disabled=not vcp_active)
    vcp_max_recent_width_pct = st.slider("Макс. ширина последней трети (%)", 3.0, 25.0, 10.0, 0.5, disabled=not vcp_active)
    vcp_min_compression_pct = st.slider("Минимальное сжатие диапазона (%)", 10.0, 70.0, 35.0, 1.0, disabled=not vcp_active)
    vcp_near_high_pct = st.slider("Цена не дальше от верха базы (%)", 2.0, 20.0, 10.0, 0.5, disabled=not vcp_active)
    vcp_dry_volume_ratio = st.slider(
        "Сухой объём: последняя треть / первые две",
        0.30,
        1.20,
        0.80,
        0.05,
        disabled=not vcp_active,
        help="0.80 значит: средний объём последней трети базы должен быть не выше 80% от среднего объёма первых двух третей.",
    )

    st.markdown('<div class="desk-section-title">Spring-отскок</div>', unsafe_allow_html=True)
    spring_support_days = st.slider("Поддержка за дней", 30, 120, 60, 5, disabled=not spring_active, help=SCANNER_HELP[SCANNER_SPRING])
    spring_low_days = st.slider("Дно смотреть за дней", 60, 250, 120, 10, disabled=not spring_active)
    spring_break_pct = st.slider("Минимальный прокол поддержки (%)", 0.1, 10.0, 0.7, 0.1, disabled=not spring_active)
    spring_reclaim_pct = st.slider("Возврат выше поддержки (%)", 0.0, 5.0, 0.2, 0.1, disabled=not spring_active)
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
    spring_max_from_low_pct = st.slider("Цена не дальше от дна периода (%)", 5.0, 80.0, 30.0, 1.0, disabled=not spring_active)

    st.markdown('<div class="desk-section-title">Pulse · что-то произошло</div>', unsafe_allow_html=True)
    momentum_direction_label = st.selectbox(
        "Направление импульса",
        list(MOMENTUM_DIRECTION_LABELS.keys()),
        index=0,
        disabled=not momentum_active,
        help="По умолчанию ищем и резкий рост, и резкое падение. Это режим события: сначала поймать интерес, дальше ты сам решаешь направление.",
    )
    momentum_direction = MOMENTUM_DIRECTION_LABELS[momentum_direction_label]
    momentum_col_1, momentum_col_2 = st.columns(2)
    with momentum_col_1:
        momentum_fast_minutes = st.slider(
            "Быстрый импульс, минут",
            3,
            10,
            3,
            1,
            disabled=not momentum_active,
            help="Короткое окно старта: здесь Pulse ищет самый первый всплеск объёма.",
        )
        momentum_min_fast_move_pct = st.slider(
            "Мин. движение за быстрое окно (%)",
            0.3,
            10.0,
            0.7,
            0.1,
            disabled=not momentum_active,
            help="Движение не главное, но оно должно подтверждать, что повышенный объём реально двигает цену.",
        )
        momentum_volume_mult = st.slider(
            "Объём быстрого окна выше нормы ×",
            1.5,
            20.0,
            6.0,
            0.5,
            disabled=not momentum_active,
            help="Главный фильтр Pulse. 6x значит: текущий объём должен быть минимум в шесть раз выше внутридневной нормы.",
        )
        momentum_min_5m_dollar_volume = st.number_input(
            "Мин. $ объём быстрого окна",
            0,
            50_000_000,
            500_000,
            50_000,
            disabled=not momentum_active,
        )
    with momentum_col_2:
        momentum_confirm_minutes = st.slider(
            "Подтверждение, минут",
            10,
            30,
            10,
            1,
            disabled=not momentum_active,
            help="Короткое подтверждение старта, чтобы не ловить одиночный случайный принт.",
        )
        momentum_min_confirm_move_pct = st.slider(
            "Мин. движение за подтверждение (%)",
            0.5,
            15.0,
            1.2,
            0.1,
            disabled=not momentum_active,
        )
        momentum_confirm_volume_mult = st.slider(
            "Объём подтверждения выше нормы ×",
            1.2,
            15.0,
            3.0,
            0.2,
            disabled=not momentum_active,
        )
        momentum_min_15m_dollar_volume = st.number_input(
            "Мин. $ объём подтверждения",
            0,
            100_000_000,
            1_250_000,
            50_000,
            disabled=not momentum_active,
        )
    momentum_volume_baseline_minutes = st.slider(
        "Норму объёма считать по предыдущим минутам",
        20,
        120,
        60,
        5,
        disabled=not momentum_active,
        help="Берём предыдущий внутридневной участок и сравниваем с ним текущий всплеск. Чем больше окно, тем спокойнее фильтр.",
    )
    momentum_min_day_dollar_volume = st.number_input(
        "Мин. $ объём с начала сессии",
        0,
        200_000_000,
        3_000_000,
        100_000,
        disabled=not momentum_active,
    )
    momentum_quality_col_1, momentum_quality_col_2 = st.columns(2)
    with momentum_quality_col_1:
        momentum_max_bar_age_minutes = st.slider(
            "Свежесть последней минутки, мин",
            1,
            15,
            2,
            1,
            disabled=not momentum_active,
            help="Если последняя минутная свеча старше этого значения, тикер не считается свежим.",
        )
        momentum_max_vwap_distance_pct = st.slider(
            "Не дальше от VWAP (%)",
            0.0,
            30.0,
            5.0,
            0.5,
            disabled=not momentum_active,
            help="Защита от слишком позднего входа: если цена уже очень далеко от VWAP, сигнал отбрасывается. 0 выключает фильтр.",
        )
        momentum_min_score = st.slider("Мин. балл Pulse", 50, 95, 85, 5, disabled=not momentum_active)
        momentum_min_quality_checks = st.slider(
            "Мин. подтверждений качества",
            2,
            6,
            3,
            1,
            disabled=not momentum_active,
            help="Дополнительный отсев мусора: VWAP, EMA 9/20, пробой 20 минут, направленные свечи, новая волна объёма, близость к VWAP.",
        )
    with momentum_quality_col_2:
        momentum_require_new_volume_wave = st.toggle(
            "Требовать новую волну объёма",
            value=True,
            disabled=not momentum_active,
            help="Главная защита от поздних сигналов: текущие минуты должны быть заметно сильнее предыдущего такого же окна.",
        )
        momentum_min_volume_acceleration = st.slider(
            "Ускорение объёма к прошлому окну ×",
            1.0,
            10.0,
            2.0,
            0.25,
            disabled=not momentum_active or not momentum_require_new_volume_wave,
        )
        momentum_max_prior_fast_rvol = st.slider(
            "Макс. RVOL прошлого окна ×",
            0.5,
            10.0,
            2.5,
            0.25,
            disabled=not momentum_active or not momentum_require_new_volume_wave,
            help="Если прошлое окно уже было горячим, это уже не начало движения, а продолжение.",
        )
        momentum_max_recent_prior_rvol = st.slider(
            "Макс. RVOL прошлых 20 минут ×",
            0.5,
            12.0,
            4.0,
            0.25,
            disabled=not momentum_active or not momentum_require_new_volume_wave,
            help="Если за последние 20 минут уже был горячий объём, новый сигнал считается не первой волной.",
        )
        momentum_min_fast_volume_share_pct = st.slider(
            "Доля быстрого объёма в подтверждении (%)",
            10.0,
            90.0,
            40.0,
            5.0,
            disabled=not momentum_active or not momentum_require_new_volume_wave,
            help="Показывает, что основной поток объёма происходит прямо сейчас, а не уже размазан по прошлым минутам.",
        )
        momentum_max_confirm_move_pct = st.slider(
            "Макс. движение подтверждения (%)",
            0.0,
            30.0,
            8.0,
            0.5,
            disabled=not momentum_active,
            help="0 выключает фильтр. По умолчанию не даём Pulse ловить слишком поздний улёт.",
        )
        momentum_require_vwap_side = st.toggle(
            "Требовать сторону VWAP",
            value=True,
            disabled=not momentum_active,
            help="Рост должен быть выше VWAP, падение ниже VWAP. Это отсеивает слабые импульсы против внутридневного потока.",
        )
        momentum_require_ema_trend = st.toggle(
            "Требовать EMA 9/20",
            value=True,
            disabled=not momentum_active,
            help="Рост должен иметь EMA9 выше EMA20, падение EMA9 ниже EMA20. Это снижает шум.",
        )
        momentum_include_extended_hours = st.toggle(
            "Pre/Post-market",
            value=False,
            disabled=not momentum_active,
            help="Включает премаркет и постмаркет в Pulse. На графике эти зоны подсвечиваются серым.",
        )

    st.markdown('<div class="desk-section-title">Цена</div>', unsafe_allow_html=True)
    price_col_1, price_col_2 = st.columns(2)
    with price_col_1:
        min_price = st.number_input(
            "Мин. цена",
            0.01,
            500.0,
            0.10 if base_impulse_only or rvol_active else (1.50 if momentum_active else 0.50),
            0.01 if base_impulse_only or rvol_active else 0.10,
        )
    with price_col_2:
        max_price = st.number_input("Макс. цена", 0.01, 500.0, 50.0 if momentum_active else 20.0, 1.0)

    st.markdown('<div class="desk-section-title">Автоматизация</div>', unsafe_allow_html=True)
    send_alerts = st.toggle("Telegram-уведомления", value=False)
    telegram_configured = bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)
    if st.button("Отправить тест Telegram", use_container_width=True, disabled=not telegram_configured):
        if send_telegram("TEST 1.00x +0%"):
            st.success("Тест отправлен.")
        else:
            st.error("Telegram не отправился. Проверь токен и chat_id.")
    if not telegram_configured:
        st.caption("Тест недоступен: нет TELEGRAM_TOKEN или TELEGRAM_CHAT_ID.")
    auto_scan_requested = st.toggle("Авто-скан", value=False)
    auto_scan_available = st_autorefresh is not None
    auto_continuous = st.toggle(
        "Авто-скан непрерывно",
        value=False,
        disabled=not auto_scan_requested or not momentum_active,
        help=(
            "Только для Импульс + объём: скан закончил пачку и почти сразу начинает следующую. "
            "Telegram успевает отправить сигналы, потому что отправка идёт внутри завершённого скана."
        ),
    )
    if not momentum_active or not auto_scan_requested:
        auto_continuous = False
    auto_scan = auto_scan_requested and (auto_scan_available or auto_continuous)
    if auto_scan_requested and not auto_scan_available and not auto_continuous:
        st.caption("Интервальный авто-скан ждёт пакет streamlit-autorefresh. Непрерывный режим работает без него.")
        if AUTOREFRESH_IMPORT_ERROR:
            st.caption(f"Ошибка авто-обновления: {AUTOREFRESH_IMPORT_ERROR[:120]}")
    elif auto_scan_requested and not momentum_active:
        st.caption("Непрерывный режим доступен только для Импульс + объём.")
    auto_interval_options = [1, 2, 3, 4, 5, 60]
    auto_interval = st.select_slider(
        "Интервал",
        options=auto_interval_options,
        value=1 if momentum_active else 5,
        format_func=lambda value: f"{value} мин",
        disabled=not auto_scan_requested or auto_continuous,
    )
    if st.button("Сбросить повторы Telegram", use_container_width=True):
        st.session_state.notified_signals = set()
        st.success("Повторы сброшены.")

# ── AUTO REFRESH ──────────────────────────────────────────────────
auto_refresh_interval_ms = (
    CONTINUOUS_AUTO_REFRESH_SECONDS * 1000 if auto_continuous else auto_interval * 60 * 1000
)
if auto_scan_requested and not auto_continuous and st_autorefresh is not None and not st.session_state.get("auto_scan_running"):
    st_autorefresh(interval=auto_refresh_interval_ms, key=f"accumulation_autorefresh_{int(auto_continuous)}")
elif auto_scan_requested and not auto_continuous and st_autorefresh is None:
    st.warning("Для интервального авто-обновления нужен пакет streamlit-autorefresh. Непрерывный режим работает без пакета.")


# ── MAIN UI ───────────────────────────────────────────────────────
status_kind, status_text = get_market_status()
status_tone = {"success": "green", "warning": "amber", "info": "blue"}.get(status_kind, "")

cfg = ScanConfig(
    scanner_mode=scanner_mode,
    min_dollar_volume=int(min_dollar_volume),
    base_impulse_enabled=base_impulse_enabled,
    base_impulse_days=base_impulse_days,
    base_width_filter_enabled=base_width_filter_enabled,
    base_max_width_pct=base_max_width_pct,
    base_volume_mult=base_volume_mult,
    base_impulse_only=base_impulse_only,
    max_stale_days=max_stale_days,
    min_price=min_price,
    max_price=max_price,
    rvol_avg_days=rvol_avg_days,
    rvol_mult=rvol_mult,
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
    momentum_direction=momentum_direction,
    momentum_fast_minutes=momentum_fast_minutes,
    momentum_confirm_minutes=momentum_confirm_minutes,
    momentum_volume_baseline_minutes=momentum_volume_baseline_minutes,
    momentum_min_fast_move_pct=momentum_min_fast_move_pct,
    momentum_min_confirm_move_pct=momentum_min_confirm_move_pct,
    momentum_volume_mult=momentum_volume_mult,
    momentum_confirm_volume_mult=momentum_confirm_volume_mult,
    momentum_min_5m_dollar_volume=int(momentum_min_5m_dollar_volume),
    momentum_min_15m_dollar_volume=int(momentum_min_15m_dollar_volume),
    momentum_min_day_dollar_volume=int(momentum_min_day_dollar_volume),
    momentum_max_bar_age_minutes=momentum_max_bar_age_minutes,
    momentum_max_vwap_distance_pct=momentum_max_vwap_distance_pct,
    momentum_require_vwap_side=momentum_require_vwap_side,
    momentum_require_ema_trend=momentum_require_ema_trend,
    momentum_include_extended_hours=momentum_include_extended_hours,
    momentum_min_score=momentum_min_score,
    momentum_min_quality_checks=momentum_min_quality_checks,
    momentum_require_new_volume_wave=momentum_require_new_volume_wave,
    momentum_min_volume_acceleration=momentum_min_volume_acceleration,
    momentum_max_prior_fast_rvol=momentum_max_prior_fast_rvol,
    momentum_max_recent_prior_rvol=momentum_max_recent_prior_rvol,
    momentum_min_fast_volume_share_pct=momentum_min_fast_volume_share_pct,
    momentum_max_confirm_move_pct=momentum_max_confirm_move_pct,
)

telegram_ready = bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)
telegram_tone = "green" if send_alerts and telegram_ready else ("red" if send_alerts else "amber")
telegram_label = "готов" if send_alerts and telegram_ready else ("нет секрета" if send_alerts else "выкл")
mode_subtitle = SCANNER_SUBTITLES.get(cfg.scanner_mode, "")
mode_label = SCANNER_LABELS.get(cfg.scanner_mode, "Скринер")
alpaca_freshness_label = "real-time" if alpaca_realtime else f"{ALPACA_SIP_DELAY_MINUTES} мин"
alpaca_freshness_tone = "green" if alpaca_realtime else "amber"

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
            chip("За прогон", format_int_cell(max_tickers)),
            chip("Цена", f"${min_price:g}-${max_price:g}"),
            chip("Открытие", "внутри вчерашней свечи", "blue"),
            chip("База", f"{cfg.base_impulse_days} св. до {cfg.base_max_width_pct:g}%" if cfg.base_width_filter_enabled else f"{cfg.base_impulse_days} св. · ширина выкл."),
            chip("RVOL", f">{cfg.base_volume_mult:g}x к макс. из {cfg.base_impulse_days}"),
            chip("Свежесть", f"{cfg.max_stale_days}д"),
            chip("Источник", DATA_SOURCE_LABELS.get(data_source, data_source), "green"),
            chip("Alpaca", alpaca_freshness_label, alpaca_freshness_tone),
        ]
    )
elif cfg.scanner_mode == SCANNER_RVOL:
    setup_chips = "".join(
        [
            chip("Режим", mode_label, "amber"),
            chip("Биржа", exchange),
            chip("За прогон", format_int_cell(max_tickers)),
            chip("Цена", f"${min_price:g}-${max_price:g}"),
            chip("Средняя", f"{cfg.rvol_avg_days} дней"),
            chip("RW", f"≥ {cfg.rvol_mult:g}x"),
            chip("Свежесть", f"{cfg.max_stale_days}д"),
            chip("Свечи/объём", DATA_SOURCE_LABELS.get(data_source, data_source), "green"),
            chip("Alpaca", alpaca_freshness_label, alpaca_freshness_tone),
            chip("Долларовый объём", format_dollar_cell(cfg.min_dollar_volume)),
        ]
    )
elif cfg.scanner_mode == SCANNER_VCP:
    setup_chips = "".join(
        [
            chip("Режим", mode_label, "blue"),
            chip("Биржа", exchange),
            chip("За прогон", format_int_cell(max_tickers)),
            chip("Цена", f"${min_price:g}-${max_price:g}"),
            chip("VCP", f"{cfg.vcp_days} дней"),
            chip("База", f"до {cfg.vcp_max_base_width_pct:g}%"),
            chip("Последняя треть", f"до {cfg.vcp_max_recent_width_pct:g}%"),
            chip("Сжатие", f"от {cfg.vcp_min_compression_pct:g}%"),
            chip("До верха", f"до {cfg.vcp_near_high_pct:g}%"),
            chip("Сухой объём", f"≤ {cfg.vcp_dry_volume_ratio:g}x"),
            chip("Свежесть", f"{cfg.max_stale_days}д"),
            chip("Свечи/объём", DATA_SOURCE_LABELS.get(data_source, data_source), "green"),
            chip("Alpaca", alpaca_freshness_label, alpaca_freshness_tone),
            chip("Долларовый объём", format_dollar_cell(cfg.min_dollar_volume)),
        ]
    )
elif cfg.scanner_mode == SCANNER_MOMENTUM:
    direction_chip = {
        MOMENTUM_DIR_BOTH: "вверх/вниз",
        MOMENTUM_DIR_UP: "только вверх",
        MOMENTUM_DIR_DOWN: "только вниз",
    }.get(cfg.momentum_direction, "вверх/вниз")
    setup_chips = "".join(
        [
            chip("Режим", mode_label, "red"),
            chip("Биржа", exchange),
            chip("За прогон", format_int_cell(max_tickers)),
            chip("Цена", f"${min_price:g}-${max_price:g}"),
            chip("Направление", direction_chip),
            chip("Импульс", f"{cfg.momentum_fast_minutes}м · {cfg.momentum_min_fast_move_pct:g}%"),
            chip("Подтверждение", f"{cfg.momentum_confirm_minutes}м · {cfg.momentum_min_confirm_move_pct:g}%"),
            chip("RVOL", f"{cfg.momentum_volume_mult:g}x/{cfg.momentum_confirm_volume_mult:g}x"),
            chip("Старт объёма", f"{cfg.momentum_min_volume_acceleration:g}x" if cfg.momentum_require_new_volume_wave else "выкл"),
            chip("Доля", f"{cfg.momentum_min_fast_volume_share_pct:g}%"),
            chip("$ быстро", format_dollar_cell(cfg.momentum_min_5m_dollar_volume)),
            chip("$ подтв.", format_dollar_cell(cfg.momentum_min_15m_dollar_volume)),
            chip("Балл", f"от {cfg.momentum_min_score}"),
            chip("Качество", f"{cfg.momentum_min_quality_checks}/6"),
            chip("Свежесть", f"до {cfg.momentum_max_bar_age_minutes}м"),
            chip("Не поздно", f"до {cfg.momentum_max_confirm_move_pct:g}%" if cfg.momentum_max_confirm_move_pct else "выкл"),
            chip("Сессия", "pre/post" if cfg.momentum_include_extended_hours else "regular"),
            chip("Alpaca", alpaca_freshness_label, alpaca_freshness_tone),
        ]
    )
elif cfg.scanner_mode == SCANNER_SPRING:
    setup_chips = "".join(
        [
            chip("Режим", mode_label, "green"),
            chip("Биржа", exchange),
            chip("За прогон", format_int_cell(max_tickers)),
            chip("Цена", f"${min_price:g}-${max_price:g}"),
            chip("Поддержка", f"{cfg.spring_support_days} дней"),
            chip("Дно", f"{cfg.spring_low_days} дней"),
            chip("Прокол", f"от {cfg.spring_break_pct:g}%"),
            chip("Возврат", f"{cfg.spring_reclaim_pct:g}%"),
            chip("Закрытие", f"верх {cfg.spring_close_position_pct:g}%"),
            chip("Объём", f"×{cfg.spring_volume_mult:g}"),
            chip("От дна", f"до {cfg.spring_max_from_low_pct:g}%"),
            chip("Свечи/объём", DATA_SOURCE_LABELS.get(data_source, data_source), "green"),
            chip("Alpaca", alpaca_freshness_label, alpaca_freshness_tone),
            chip("Долларовый объём", format_dollar_cell(cfg.min_dollar_volume)),
        ]
    )
else:
    setup_chips = chip("Режим", mode_label, "blue")
st.markdown(
    f"""
    <div class="desk-filter-board">
        <div class="desk-filter-title">Параметры скана</div>
        <div class="desk-chipbar">{setup_chips}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

render_market_overview(data_source, alpaca_realtime)

if data_source == DATA_SOURCE_AUTO and yf is None:
    st.warning("yfinance не установлен. Резерв Yahoo недоступен; текущий скан пойдёт через Alpaca.")
if send_alerts and not telegram_ready:
    st.warning(
        "Telegram включён, но TELEGRAM_TOKEN или TELEGRAM_CHAT_ID не найдены в Streamlit secrets. "
        "В таком режиме уведомления в бот отправляться не будут."
    )

batch_size = int(max_tickers)
auto_running = bool(st.session_state.get("auto_scan_running"))
if auto_scan:
    current = now_et()
    if auto_running:
        should_auto_run = False
        auto_text = (
            f"Авто-скан: текущая пачка уже выполняется · "
            f"пачка {format_int_cell(batch_size)} акций · рынок до {format_int_cell(AUTO_SCAN_MARKET_LIMIT)}"
        )
    elif auto_continuous:
        should_auto_run = True
        last_auto_total = int(st.session_state.last_auto_total or 0)
        next_range_hint = ""
        if last_auto_total > 0:
            next_start = min(int(st.session_state.auto_scan_offset or 0), max(0, last_auto_total - 1))
            next_end = min(next_start + batch_size, last_auto_total)
            next_range_hint = (
                f" · следующая пачка: {format_int_cell(next_start + 1)}-"
                f"{format_int_cell(next_end)} из {format_int_cell(last_auto_total)}"
            )
        auto_text = (
            f"Непрерывный авто-скан: после завершения пачки сразу идёт следующая · "
            f"пауза {CONTINUOUS_AUTO_REFRESH_SECONDS} сек · "
            f"пачка {format_int_cell(batch_size)} акций · рынок до {format_int_cell(AUTO_SCAN_MARKET_LIMIT)}"
            f"{next_range_hint}"
        )
    elif st.session_state.auto_last_run:
        elapsed_sec = int((current - st.session_state.auto_last_run).total_seconds())
        remaining = max(0, auto_interval * 60 - elapsed_sec)
        should_auto_run = elapsed_sec >= auto_interval * 60
        last_auto_total = int(st.session_state.last_auto_total or 0)
        next_range_hint = ""
        if last_auto_total > 0:
            next_start = min(int(st.session_state.auto_scan_offset or 0), max(0, last_auto_total - 1))
            next_end = min(next_start + batch_size, last_auto_total)
            next_range_hint = (
                f" · следующая пачка: {format_int_cell(next_start + 1)}-"
                f"{format_int_cell(next_end)} из {format_int_cell(last_auto_total)}"
            )
        auto_text = (
            f"Авто-скан: каждые {auto_interval} мин · последний {elapsed_sec // 60} мин назад · "
            f"следующий через {remaining // 60} мин · пачка {format_int_cell(batch_size)} акций · "
            f"рынок до {format_int_cell(AUTO_SCAN_MARKET_LIMIT)}{next_range_hint}"
        )
    else:
        should_auto_run = True
        auto_text = (
            f"Авто-скан: каждые {auto_interval} мин · первый запуск ожидается · "
            f"пачка {format_int_cell(batch_size)} акций · рынок до {format_int_cell(AUTO_SCAN_MARKET_LIMIT)}"
        )
else:
    should_auto_run = False
    auto_text = f"Ручной запуск: проверит первые {format_int_cell(batch_size)} акций и остановится."

last_scan_seconds = int(st.session_state.get("last_scan_seconds") or 0)
if auto_scan_requested and last_scan_seconds > 0:
    auto_text += f" · последний скан {format_seconds(last_scan_seconds)}"
    if not auto_continuous and last_scan_seconds >= int(auto_interval) * 60:
        auto_text += " · скан дольше интервала — выбери интервал больше или уменьши пачку"

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
        st.session_state.ai_analysis_result = {}
        st.session_state.ai_analysis_error = ""
        st.rerun()


dismissed_now = active_dismissed_tickers()
dismissed_flash = str(st.session_state.get("last_dismissed_ticker") or "")
if dismissed_flash:
    if hasattr(st, "toast"):
        st.toast(f"Скрыто на {DISMISS_TTL_HOURS} часов: {dismissed_flash}")
    st.session_state.last_dismissed_ticker = ""
if dismissed_now:
    preview = ", ".join(
        f"{ticker} до {expiry.strftime('%H:%M')}"
        for ticker, expiry in sorted(dismissed_now.items())[:10]
    )
    if len(dismissed_now) > 10:
        preview += f" +{len(dismissed_now) - 10}"
    hidden_col, restore_col = st.columns([0.78, 0.22])
    with hidden_col:
        st.caption(f"Скрыты на {DISMISS_TTL_HOURS} часов: {preview}")
    with restore_col:
        if st.button("Вернуть скрытые", use_container_width=True):
            st.session_state.dismissed_tickers = {}
            rerun_app()


if (start_scan and not auto_running) or (auto_scan and should_auto_run and not auto_running):
    is_auto_batch = bool(auto_scan and should_auto_run and not start_scan and not auto_running)
    if is_auto_batch:
        st.session_state.auto_scan_running = True
        st.session_state.auto_scan_started_at = now_et()
    all_tickers_full = get_nasdaq_tickers(exchange, max_scan_price)
    batch_size = max(1, int(max_tickers))

    if is_auto_batch:
        all_tickers = all_tickers_full[:AUTO_SCAN_MARKET_LIMIT]
        auto_signature = (
            f"{cfg.scanner_mode}:{exchange}:{max_scan_price:g}:{AUTO_SCAN_MARKET_LIMIT}:"
            f"{data_source}:{int(alpaca_realtime)}:{batch_size}:{int(auto_continuous)}:{int(send_alerts)}"
        )
        if st.session_state.auto_scan_signature != auto_signature:
            st.session_state.auto_scan_signature = auto_signature
            st.session_state.auto_scan_offset = 0

        scan_start = int(st.session_state.auto_scan_offset or 0)
        if scan_start >= len(all_tickers):
            scan_start = 0
        scan_end = min(scan_start + batch_size, len(all_tickers))
        ticker_infos = all_tickers[scan_start:scan_end]
        scan_scope = (
            f"авто {format_int_cell(scan_start + 1)}-{format_int_cell(scan_end)} "
            f"из {format_int_cell(len(all_tickers))}"
        )
        st.session_state.last_auto_total = len(all_tickers)
    else:
        all_tickers = all_tickers_full
        scan_start = 0
        scan_end = min(batch_size, len(all_tickers))
        ticker_infos = all_tickers[:scan_end]
        scan_scope = f"ручной первые {format_int_cell(len(ticker_infos))} из {format_int_cell(len(all_tickers))}"

    if not ticker_infos:
        st.error("Нет тикеров для сканирования.")
    else:
        progress_box = st.progress(0.0)
        status_box = st.empty()
        table_box = st.empty()

        active_old_results = clear_new_scan_flags(
            filter_results_for_config(
                st.session_state.results,
                cfg,
                data_source,
                alpaca_realtime,
                hide_dismissed=False,
            )
        )
        remember_seen_results(active_old_results)

        hits = scan_market(
            ticker_infos=ticker_infos,
            cfg=cfg,
            data_source=data_source,
            alpaca_realtime=alpaca_realtime,
            progress_box=progress_box,
            status_box=status_box,
            table_box=table_box,
            send_alerts=send_alerts,
        )
        hits = mark_new_scan_results(hits)

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
            elapsed_text = str(st.session_state.get("last_scan_elapsed") or "")
            elapsed_part = f" · время {elapsed_text}" if elapsed_text else ""
            done_message = (
                f"Готово: найдено {format_int_cell(len(hits))} сигналов · "
                f"проверено {format_int_cell(len(ticker_infos))} · {scan_scope}{elapsed_part}"
            )
            status_box.success(done_message)
            if hasattr(st, "toast"):
                st.toast(done_message, icon="✅")
        else:
            elapsed_text = str(st.session_state.get("last_scan_elapsed") or "")
            elapsed_part = f" · время {elapsed_text}" if elapsed_text else ""
            done_message = f"Скан завершён: сигналов нет · проверено {format_int_cell(len(ticker_infos))} · {scan_scope}{elapsed_part}"
            status_box.info(done_message)
            if hasattr(st, "toast") and not is_auto_batch:
                st.toast(done_message, icon="ℹ️")

        if st.session_state.scan_errors:
            with st.expander("Диагностика"):
                st.write("\n".join(st.session_state.scan_errors))

    if is_auto_batch:
        st.session_state.auto_scan_running = False
        st.session_state.auto_scan_started_at = None

visible_results = sort_results(
    filter_results_for_config(st.session_state.results, cfg, data_source, alpaca_realtime),
    cfg.base_impulse_only,
)

if visible_results:
    render_results_summary(visible_results)
    render_results_table(visible_results, cfg)
    render_ai_analysis_panel(visible_results, cfg)
    render_signal_gallery(visible_results, alpaca_realtime)

    csv = display_frame(visible_results, cfg.base_impulse_only, include_chart=False).to_csv(index=False).encode("utf-8")
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

if auto_scan_requested and auto_continuous and not st.session_state.get("auto_scan_running"):
    time.sleep(CONTINUOUS_AUTO_REFRESH_SECONDS)
    rerun_app()

