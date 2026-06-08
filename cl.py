import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time
from datetime import datetime
import threading
import subprocess
import platform

# ── TELEGRAM CONFIG ─────────────────────────────────────────────
TELEGRAM_TOKEN   = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False

st.set_page_config(page_title="Breakout Screener", page_icon="📈", layout="wide")
st.title("📈 Breakout Screener")

with st.sidebar:
    st.header("🎯 Режим поиска")
    mode = st.radio("Выбери режим:", ["🔴 СТРОГИЙ — точный паттерн", "🟡 МЯГКИЙ — больше акций"], index=0)
    st.divider()
    st.subheader("⚙️ Параметры")
    if "СТРОГИЙ" in mode:
        default_vol, default_channel, default_breakout = 5.0, 8.0, 15.0
        st.info("Канал 15 свечей · ширина ≤8% · объём ×5+ · пробой ≥15%")
    else:
        default_vol, default_channel, default_breakout = 2.0, 15.0, 5.0
        st.info("Канал 15 свечей · ширина ≤15% · объём ×2+ · пробой ≥5%")
    st.divider()
    st.subheader("💲 Цена акции")
    max_price_up = st.number_input("Макс. цена BREAKOUT ↑ ($)", 0.001, 500.0, 10.0, 1.0)
    max_price_dn = st.number_input("Макс. цена BREAKDOWN ↓ ($)", 0.001, 500.0, 100.0, 5.0)
    min_days = 15
    min_vol = st.select_slider("Мин. рост объёма", options=[2.0, 3.0, 5.0, 7.0, 10.0], value=default_vol, format_func=lambda x: f"× {x}")
    channel_pct = st.slider("Ширина канала (%)", 2, 25, int(default_channel))
    min_breakout = st.slider("Мин. пробой (%)", 2, 50, int(default_breakout))
    st.divider()
    st.subheader("🕐 Торговая сессия")
    sess_premarket  = st.checkbox("🌅 Pre-Market  (4:00–9:30 ET)", value=False)
    sess_regular    = st.checkbox("📈 Дневная сессия (9:30–16:00 ET)", value=True)
    sess_postmarket = st.checkbox("🌙 Post-Market (16:00–20:00 ET)", value=False)
    if not sess_premarket and not sess_regular and not sess_postmarket:
        st.warning("Выбери хотя бы одну сессию!")
    st.divider()
    exchange = st.selectbox("Биржа", ["ALL", "NASDAQ", "NYSE", "AMEX"])
    signal_type = st.selectbox("Тип сигнала", ["ALL", "BREAKOUT ↑", "BREAKDOWN ↓", "ОБЪЁМ 🔥"], index=0)
    st.divider()
    st.subheader("🎯 Опционы")
    options_filter = st.checkbox("Только акции с опционами (для BREAKDOWN ↓)", value=False)
    if options_filter:
        st.info("⚠️ Замедляет сканирование ~0.5 сек на акцию")
    max_tickers = st.slider("Акций за прогон", 50, 5000, 500, 50)
    st.divider()
    st.subheader("⏰ Авто-сканирование")
    auto_scan = st.toggle("Включить авто-поиск", value=False)
    auto_interval = st.select_slider("Интервал", options=[5,10,15,30,60], value=15, format_func=lambda x: f"каждые {x} мин", disabled=not auto_scan)
    notify_sound = st.checkbox("🔔 Звук на компьютере", value=True, disabled=not auto_scan)
    st.success("📱 Telegram @breakout_mak_bot подключён!")
    st.divider()
    st.caption("Данные: Yahoo Finance · 30 торговых свечей · канал 15 дней")


@st.cache_data(ttl=3600, show_spinner=False)
def get_tickers(exchange="ALL", max_price_up=10.0, max_price_dn=100.0):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json", "Referer": "https://www.nasdaq.com/",
    }
    exchanges = ["nasdaq", "nyse", "amex"] if exchange == "ALL" else [exchange.lower()]
    tickers, seen = [], set()
    max_price_global = max(max_price_up, max_price_dn)
    for ex in exchanges:
        try:
            url = f"https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&exchange={ex}"
            r = requests.get(url, headers=headers, timeout=20)
            rows = r.json().get("data", {}).get("table", {}).get("rows", []) or []
            for row in rows:
                sym = (row.get("symbol") or "").strip()
                if not sym or not sym.isalpha() or len(sym) > 5 or sym in seen:
                    continue
                try:
                    price = float((row.get("lastsale") or "").replace("$", "").strip())
                    if price <= 0 or price > max_price_global:
                        continue
                except Exception:
                    continue
                seen.add(sym)
                tickers.append({"ticker": sym, "exchange": ex.upper(), "name": row.get("name", ""), "price_api": price})
        except Exception:
            pass
    if len(tickers) < 50:
        fallback = ['SNDL','GNUS','CTRM','HCDI','EXPR','CLPS','SESN','IDEX','SENS','VERB',
            'ATER','BBIG','IMPP','SHIP','AMMO','ZFOX','MULN','DPRO','GOVX','CIDM',
            'BIVI','AULT','NOVN','PBTS','ATNF','MIST','QNRX','MOXC','HYMC','CLNN',
            'SPHL','NAKD','PROG','BOXL','FFIE','MARK','WISA','VBIV','GLYC','ZKIN',
            'BNGO','NKLA','BLNK','GOEV','RIDE','WKHS','SOLO','CLOV','WISH','MVIS',
            'AMC','BB','NOK','SIRI','LCID','RIVN','XPEV','LI','NIO','TLRY']
        tickers = [{"ticker": t, "exchange": "US", "name": "", "price_api": 0} for t in fallback]
    return tickers


def fetch_history(ticker, session="regular"):
    try:
        if session == "regular":
            df = yf.download(ticker, period="45d", interval="1d", auto_adjust=True, progress=False, timeout=10)
            if df is None or len(df) < 15: return None
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            return df.dropna(subset=["Close", "Volume"])
        else:
            df = yf.download(ticker, period="5d", interval="1m", auto_adjust=True, prepost=True, progress=False, timeout=10)
            if df is None or len(df) < 10: return None
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.index = pd.to_datetime(df.index)
            import datetime as dt
            if session == "premarket":
                df = df[(df.index.time >= dt.time(4,0)) & (df.index.time < dt.time(9,30))]
            else:
                df = df[(df.index.time > dt.time(16,0)) & (df.index.time <= dt.time(20,0))]
            if len(df) < 10: return None
            return df.resample("5min").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
    except Exception:
        return None


def has_options(ticker):
    try:
        return len(yf.Ticker(ticker).options) > 0
    except Exception:
        return False


def find_flat_base(closes, min_days, channel_pct):
    n = len(closes)
    if n < min_days + 1: return None
    end = n - 2
    start = end - min_days + 1
    if start < 0: return None
    window = closes[start: end + 1]
    if len(window) < min_days: return None
    mn = float(window.min())
    mx = float(window.max())
    if mn <= 0: return None
    if (mx - mn) / mn * 100 > channel_pct: return None
    return (start, end, mn, mx)


def analyze(ticker_info, cfg, session="regular"):
    df = fetch_history(ticker_info["ticker"], session)
    if df is None: return None
    closes  = df["Close"].squeeze()
    volumes = df["Volume"].squeeze()
    last_price = float(closes.iloc[-1])
    last_vol   = float(volumes.iloc[-1])
    if last_price <= 0: return None

    channel = find_flat_base(closes, cfg["min_days"], cfg["channel_pct"])
    if channel is None: return None
    start_idx, end_idx, ch_min, ch_max = channel
    accum_days = end_idx - start_idx + 1

    breakout_pct  = (last_price - ch_max) / ch_max * 100
    breakdown_pct = (ch_min - last_price) / ch_min * 100

    if breakout_pct >= cfg["min_breakout"]:
        sig_type, change_pct = "BREAKOUT ↑", round(breakout_pct, 1)
    elif breakdown_pct >= cfg["min_breakout"]:
        sig_type, change_pct = "BREAKDOWN ↓", round(breakdown_pct, 1)
    else:
        sig_type, change_pct = None, 0.0

    # Объём за последние 15 торговых свечей
    prev_vols = volumes.iloc[-16:-1]
    prev_vols = prev_vols[prev_vols > 0]
    if len(prev_vols) < 10: return None
    avg_vol_15 = float(prev_vols.mean())
    vol_mult = last_vol / avg_vol_15 if avg_vol_15 > 0 else 0
    if vol_mult < cfg["min_vol"]: return None

    # Нет пробоя но объём вырос — ранний сигнал
    if sig_type is None:
        sig_type = "ОБЪЁМ 🔥"
        change_pct = 0.0

    if cfg["signal_type"] != "ALL" and cfg["signal_type"] != sig_type: return None
    if "↑" in sig_type and last_price > cfg["max_price_up"]: return None
    if "↓" in sig_type and last_price > cfg["max_price_dn"]: return None
    if cfg.get("options_only") and "↓" in sig_type:
        if not has_options(ticker_info["ticker"]): return None

    today_open = float(df["Open"].iloc[-1])
    today_body = abs(last_price - today_open) / today_open * 100
    if cfg["strict"] and today_body < 3: return None

    return {
        "Тикер": ticker_info["ticker"], "Название": ticker_info.get("name","")[:30],
        "Биржа": ticker_info.get("exchange",""), "Цена $": round(last_price, 4),
        "Сигнал": sig_type,
        "Пробой %": f"+{change_pct}%" if sig_type == "BREAKOUT ↑" else (f"-{change_pct}%" if sig_type == "BREAKDOWN ↓" else "—"),
        "Объём ×": round(vol_mult, 1), "Дней в канале": accum_days,
        "Канал": f"${round(ch_min,4)} – ${round(ch_max,4)}",
        "Тело свечи %": round(today_body, 1),
        "Опционы": "✅" if cfg.get("options_only") else "—",
        "Сессия": session.upper(), "Время": datetime.now().strftime("%H:%M:%S"),
    }


def play_sound():
    try:
        if platform.system() == "Darwin":
            subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], timeout=3)
    except Exception:
        pass


if "auto_last_run" not in st.session_state: st.session_state.auto_last_run = None
if "auto_count" not in st.session_state: st.session_state.auto_count = 0
if "stats" not in st.session_state:
    st.session_state.stats = {"checked": 0, "up": 0, "down": 0}
    st.session_state.results = []

m1, m2, m3, m4 = st.columns(4)
m1.metric("Проверено", st.session_state.stats["checked"])
m2.metric("↑ Пробоев вверх", st.session_state.stats["up"])
m3.metric("↓ Пробоев вниз", st.session_state.stats["down"])
m4.metric("Всего найдено", len(st.session_state.results))
st.divider()

if auto_scan:
    now_ts = datetime.now()
    t1, t2, t3 = st.columns(3)
    t1.info(f"⏰ Авто-поиск: каждые **{auto_interval} мин**")
    if st.session_state.auto_last_run:
        elapsed = int((now_ts - st.session_state.auto_last_run).total_seconds() // 60)
        t2.info(f"🕐 Последний запуск: **{elapsed} мин назад**")
    else:
        t2.info("🕐 Ещё не запускался")
    t3.info(f"🔄 Прогонов: **{st.session_state.auto_count}**")
    should_auto_run = st.session_state.auto_last_run is None or \
        (now_ts - st.session_state.auto_last_run).total_seconds() >= auto_interval * 60
    st.markdown('<meta http-equiv="refresh" content="60">', unsafe_allow_html=True)
else:
    should_auto_run = False

st.divider()
btn_col, info_col = st.columns([1, 3])
with btn_col:
    start = st.button("🔍 Сканировать", type="primary", use_container_width=True)
with info_col:
    minute = datetime.now().hour * 60 + datetime.now().minute
    if 4*60 <= minute < 9*60+30: st.info("🌅 Pre-Market активен (4:00–9:30 ET)")
    elif 9*60+30 <= minute <= 16*60: st.success("🟢 Основная сессия открыта (9:30–16:00 ET)")
    elif 16*60 < minute <= 20*60: st.info("🌙 Post-Market активен (16:00–20:00 ET)")
    else: st.warning("💤 Рынок закрыт — данные по последнему закрытию")

if start or (auto_scan and should_auto_run):
    cfg = {
        "max_price_up": max_price_up, "max_price_dn": max_price_dn,
        "min_days": min_days, "min_vol": min_vol, "channel_pct": channel_pct,
        "min_breakout": min_breakout, "signal_type": signal_type,
        "strict": "СТРОГИЙ" in mode, "options_only": options_filter,
        "sessions": [s for s, a in [("premarket", sess_premarket), ("regular", sess_regular), ("postmarket", sess_postmarket)] if a],
    }
    st.session_state.results = []
    st.session_state.stats = {"checked": 0, "up": 0, "down": 0}
    with st.spinner("Загружаем список тикеров..."):
        all_tickers = get_tickers(exchange, max_price_up, max_price_dn)
    scan_list = all_tickers[:max_tickers]
    st.info(f"Тикеров: **{len(all_tickers)}** | Проверяем: **{len(scan_list)}**")
    progress = st.progress(0)
    status = st.empty()
    table_box = st.empty()
    hits = []
    sessions = cfg.get("sessions", ["regular"])
    total_ops = len(scan_list) * len(sessions)
    op = 0
    for session in sessions:
        sess_label = {"premarket":"🌅 Pre-Market","regular":"📈 Дневная","postmarket":"🌙 Post-Market"}[session]
        for i, t in enumerate(scan_list):
            op += 1
            progress.progress(op / total_ops)
            status.caption(f"{sess_label} | ⏳ {t['ticker']} ({i+1}/{len(scan_list)}) · найдено: {len(hits)}")
            try:
                r = analyze(t, cfg, session)
                if r:
                    hits.append(r)
                    if "↑" in r["Сигнал"]: st.session_state.stats["up"] += 1
                    elif "↓" in r["Сигнал"]: st.session_state.stats["down"] += 1
                    table_box.dataframe(pd.DataFrame(hits), use_container_width=True, hide_index=True)
            except Exception:
                pass
            st.session_state.stats["checked"] = op
            time.sleep(0.15)

    st.session_state.results = hits
    st.session_state.auto_last_run = datetime.now()
    st.session_state.auto_count += 1
    progress.progress(1.0)

    if hits:
        if auto_scan and notify_sound: play_sound()
        lines = ["📈 <b>BREAKOUT SCREENER — найдены сигналы!</b>", ""]
        for h in hits:
            icon = "🟢" if "↑" in h["Сигнал"] else ("🔴" if "↓" in h["Сигнал"] else "🔥")
            lines.append(f"{icon} <b>{h['Тикер']}</b>  ${h['Цена $']}  {h['Пробой %']}  | Объём ×{h['Объём ×']}  | {h['Дней в канале']} дн.")
        lines += ["", f"⏰ {datetime.now().strftime('%H:%M ET')}", f"📊 Проверено: {len(scan_list)}"]
        ok = send_telegram("\n".join(lines))
        st.toast("📱 Отправлено в Telegram!", icon="✅") if ok else st.toast("⚠️ Telegram недоступен", icon="⚠️")
        st.success(f"🚨 НАЙДЕНО {len(hits)} СИГНАЛОВ!")
    else:
        if auto_scan: st.toast(f"Сигналов нет ({datetime.now().strftime('%H:%M')})")

    status.success(f"✅ Готово! Проверено {len(scan_list)} · Найдено: {len(hits)}")
    if hits:
        csv = pd.DataFrame(hits).to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Скачать CSV", data=csv, file_name=f"breakout_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")

elif st.session_state.results:
    st.subheader(f"Последние результаты — {len(st.session_state.results)} сигналов")
    st.dataframe(pd.DataFrame(st.session_state.results), use_container_width=True, hide_index=True)
    csv = pd.DataFrame(st.session_state.results).to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Скачать CSV", data=csv, file_name=f"breakout_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")
else:
    st.info("👆 Нажми «Сканировать» для начала поиска")
