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
    """Отправляет сообщение в Telegram."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        return False

st.set_page_config(page_title="Breakout Screener", page_icon="📈", layout="wide")



st.title("📈 Breakout Screener")
st.caption("Поиск паттерна: долгое плоское накопление → резкий пробой с объёмом")

# ── PRESET MODES ────────────────────────────────────────────────
with st.sidebar:
    st.header("🎯 Режим поиска")

    mode = st.radio(
        "Выбери режим:",
        ["🔴 СТРОГИЙ — точный паттерн", "🟡 МЯГКИЙ — больше акций"],
        index=0
    )

    st.divider()
    st.subheader("⚙️ Параметры")

    if "СТРОГИЙ" in mode:
        # Строгий: точно как на картинках
        default_days     = 20
        default_vol      = 5.0
        default_channel  = 8.0
        default_breakout = 15.0
        st.info("Ищем точно как на скриншотах:\n- канал ≥20 дней\n- ширина канала ≤8%\n- объём ×5+\n- пробой ≥15%")
    else:
        # Мягкий: больше результатов
        default_days     = 10
        default_vol      = 2.0
        default_channel  = 15.0
        default_breakout = 5.0
        st.info("Более широкий поиск:\n- канал ≥10 дней\n- ширина канала ≤15%\n- объём ×2+\n- пробой ≥5%")

    st.divider()

    st.subheader("💲 Цена акции")
    max_price_up = st.number_input("Макс. цена BREAKOUT ↑ ($)", 0.001, 500.0, 10.0, 1.0,
                                   help="Пробой вверх — ищем дешёвые акции")
    max_price_dn = st.number_input("Макс. цена BREAKDOWN ↓ ($)", 0.001, 500.0, 100.0, 5.0,
                                   help="Пробой вниз с опционами — можно дороже")

    min_days = st.slider("Мин. дней в канале", 5, 60, default_days,
                         help="Сколько дней акция стояла в узком диапазоне")

    min_vol = st.select_slider("Мин. рост объёма",
                               options=[1.5, 2.0, 3.0, 5.0, 7.0, 10.0],
                               value=default_vol,
                               format_func=lambda x: f"× {x}")

    channel_pct = st.slider("Ширина канала (%)", 2, 25, int(default_channel),
                            help="Чем меньше % — тем 'площе' должен быть канал")

    min_breakout = st.slider("Мин. пробой (%)", 2, 50, int(default_breakout),
                             help="На сколько % цена вышла за канал в последний день")

    st.divider()
    st.subheader("🕐 Торговая сессия")
    sess_premarket  = st.checkbox("🌅 Pre-Market  (4:00–9:30 ET)",  value=False)
    sess_regular    = st.checkbox("📈 Дневная сессия (9:30–16:00 ET)", value=True)
    sess_postmarket = st.checkbox("🌙 Post-Market (16:00–20:00 ET)", value=False)

    if not sess_premarket and not sess_regular and not sess_postmarket:
        st.warning("Выбери хотя бы одну сессию!")

    st.divider()
    exchange = st.selectbox("Биржа", ["ALL", "NASDAQ", "NYSE", "AMEX"])

    signal_type = st.selectbox("Тип сигнала",
                               ["ALL", "BREAKOUT ↑", "BREAKDOWN ↓"],
                               index=0)

    st.divider()
    st.subheader("🎯 Опционы")
    options_filter = st.checkbox(
        "Только акции с опционами",
        value=False,
        help="Для BREAKDOWN ↓ — покупка PUT опционов.\nПроверяется через Yahoo Finance."
    )
    if options_filter:
        st.info("⚠️ Проверка опционов замедляет сканирование — по ~0.5 сек на акцию")

    max_tickers = st.slider("Акций за прогон", 50, 5000, 500, 50)

    st.divider()
    st.subheader("⏰ Авто-сканирование")
    auto_scan = st.toggle("Включить авто-поиск", value=False)
    auto_interval = st.select_slider(
        "Интервал обновления",
        options=[5, 10, 15, 30, 60],
        value=15,
        format_func=lambda x: f"каждые {x} мин",
        disabled=not auto_scan
    )
    notify_sound = st.checkbox("🔔 Звук на компьютере", value=True, disabled=not auto_scan)
    st.success("📱 Telegram @breakout_mak_bot подключён!")

    st.divider()
    st.caption("Данные: Yahoo Finance\nОбновляются при каждом запуске")


# ── FUNCTIONS ───────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def get_tickers(exchange="ALL", max_price_up=10.0, max_price_dn=100.0):
    """
    Загружает тикеры с NASDAQ API и сразу фильтрует по цене.
    Так мы не тратим время на акции за $100-$500 которые нам не нужны.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.nasdaq.com/",
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
                # Фильтруем по цене прямо из API ответа
                try:
                    price_str = (row.get("lastsale") or "").replace("$", "").strip()
                    price = float(price_str)
                    if price <= 0 or price > max_price_global:
                        continue  # пропускаем дорогие акции сразу!
                except Exception:
                    continue  # если цена не парсится — пропускаем
                seen.add(sym)
                tickers.append({
                    "ticker": sym,
                    "exchange": ex.upper(),
                    "name": row.get("name", ""),
                    "price_api": price,
                })
        except Exception:
            pass

    if len(tickers) < 50:
        # Fallback список если NASDAQ API недоступен
        fallback = [
            'SNDL','GNUS','CTRM','HCDI','EXPR','CLPS','SESN','IDEX','SENS','VERB',
            'ATER','BBIG','IMPP','SHIP','AMMO','ZFOX','MULN','DPRO','GOVX','CIDM',
            'BIVI','AULT','NOVN','PBTS','ATNF','MIST','QNRX','MOXC','HYMC','CLNN',
            'SPHL','NAKD','PROG','BOXL','FFIE','MARK','WISA','VBIV','GLYC','ZKIN',
            'BNGO','NKLA','BLNK','GOEV','RIDE','WKHS','SOLO','CLOV','WISH','MVIS',
            'AMC','BB','NOK','SIRI','LCID','RIVN','XPEV','LI','NIO','TLRY',
            'ACB','CGC','CRON','NVAX','OCGN','VXRT','IOVA','CASI','BCRX','HRTX',
            'DARE','IDRA','KALA','NKTR','ORMP','PHAT','PULM','SLDB','GRWG','INVU',
            'CEMI','BNTC','EYEG','ADMP','LRMR','ITRM','CLDX','NEOS','ACST','EVFM',
        ]
        tickers = [{"ticker": t, "exchange": "US", "name": "", "price_api": 0} 
                   for t in fallback]

    return tickers


def fetch_history(ticker, session="regular"):
    """
    Загружает историю с учётом сессии:
    - regular:    дневные свечи 1d за 90 дней (основная сессия)
    - premarket:  минутные свечи за 5 дней с prepost=True, берём только 4:00-9:29
    - postmarket: минутные свечи за 5 дней с prepost=True, берём только 16:01-20:00
    """
    try:
        if session == "regular":
            df = yf.download(ticker, period="90d", interval="1d",
                             auto_adjust=True, progress=False, timeout=10)
            if df is None or len(df) < 20:
                return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df.dropna(subset=["Close", "Volume"])

        elif session == "premarket":
            df = yf.download(ticker, period="5d", interval="1m",
                             auto_adjust=True, prepost=True,
                             progress=False, timeout=10)
            if df is None or len(df) < 10:
                return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.index = pd.to_datetime(df.index)
            # Берём только pre-market часы 4:00-9:29
            df = df[df.index.time >= __import__("datetime").time(4, 0)]
            df = df[df.index.time < __import__("datetime").time(9, 30)]
            if len(df) < 10:
                return None
            # Ресемплируем в 5-минутки для анализа
            df = df.resample("5min").agg({
                "Open": "first", "High": "max",
                "Low": "min", "Close": "last", "Volume": "sum"
            }).dropna()
            return df

        elif session == "postmarket":
            df = yf.download(ticker, period="5d", interval="1m",
                             auto_adjust=True, prepost=True,
                             progress=False, timeout=10)
            if df is None or len(df) < 10:
                return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.index = pd.to_datetime(df.index)
            # Берём только after-hours 16:01-20:00
            df = df[df.index.time > __import__("datetime").time(16, 0)]
            df = df[df.index.time <= __import__("datetime").time(20, 0)]
            if len(df) < 10:
                return None
            df = df.resample("5min").agg({
                "Open": "first", "High": "max",
                "Low": "min", "Close": "last", "Volume": "sum"
            }).dropna()
            return df

    except Exception:
        return None


def has_options(ticker):
    """Проверяет наличие опционов у акции через Yahoo Finance."""
    try:
        t = yf.Ticker(ticker)
        return len(t.options) > 0
    except Exception:
        return False


def find_flat_base(closes, min_days, channel_pct):
    """
    Ищет самый длинный ПЛОСКИЙ участок ДО последней свечи.
    Именно как на картинках — акция стоит на месте много дней.
    """
    n = len(closes)
    if n < min_days + 2:
        return None

    best, best_len = None, 0

    for end in range(n - 2, min_days - 2, -1):
        start = end
        while start > 0:
            window = closes[start - 1: end + 1]
            mn, mx = float(window.min()), float(window.max())
            if mn <= 0:
                break
            rng = (mx - mn) / mn * 100
            if rng > channel_pct:
                break
            start -= 1
        length = end - start + 1
        if length >= min_days and length > best_len:
            best_len = length
            w = closes[start: end + 1]
            best = (start, end, float(w.min()), float(w.max()))

    return best


def analyze(ticker_info, cfg, session="regular"):
    df = fetch_history(ticker_info["ticker"], session)
    if df is None:
        return None

    closes  = df["Close"].squeeze()
    volumes = df["Volume"].squeeze()

    last_price = float(closes.iloc[-1])
    last_vol   = float(volumes.iloc[-1])

    # 1. Фильтр по цене (разный для BREAKOUT и BREAKDOWN)
    # Сначала быстро определяем направление пробоя по каналу
    if last_price <= 0:
        return None
    # Предварительная проверка цены — точная будет после определения сигнала

    # 2. Ищем плоский канал накопления
    channel = find_flat_base(closes, cfg["min_days"], cfg["channel_pct"])
    if channel is None:
        return None

    start_idx, end_idx, ch_min, ch_max = channel
    accum_days = end_idx - start_idx + 1

    # 3. Проверяем пробой последней свечи
    breakout_pct  = (last_price - ch_max) / ch_max * 100
    breakdown_pct = (ch_min - last_price) / ch_min * 100

    if breakout_pct >= cfg["min_breakout"]:
        sig_type   = "BREAKOUT ↑"
        change_pct = round(breakout_pct, 1)
    elif breakdown_pct >= cfg["min_breakout"]:
        sig_type   = "BREAKDOWN ↓"
        change_pct = round(breakdown_pct, 1)
    else:
        return None

    # Фильтр по типу
    if cfg["signal_type"] != "ALL" and cfg["signal_type"] != sig_type:
        return None

    # Фильтр цены по типу сигнала
    if "↑" in sig_type and last_price > cfg["max_price_up"]:
        return None
    if "↓" in sig_type and last_price > cfg["max_price_dn"]:
        return None

    # 3.5 Фильтр по опционам (только для BREAKDOWN)
    if cfg.get("options_only") and "↓" in sig_type:
        if not has_options(ticker_info["ticker"]):
            return None

    # 4. Проверяем объём — сегодня vs среднее за 10 предыдущих дней
    prev_vols = volumes.iloc[-12:-1]
    prev_vols = prev_vols[prev_vols > 0]
    if len(prev_vols) < 3:
        return None
    avg_vol  = float(prev_vols.mean())
    vol_mult = last_vol / avg_vol if avg_vol > 0 else 0

    if vol_mult < cfg["min_vol"]:
        return None

    # 5. Дополнительная проверка: СЕГОДНЯШНЯЯ свеча большая?
    # (как на картинках — большая зелёная свеча)
    today_open  = float(df["Open"].iloc[-1])
    today_body  = abs(last_price - today_open) / today_open * 100
    # Для строгого режима тело свечи должно быть заметным
    if cfg["strict"] and today_body < 3:
        return None

    return {
        "Тикер":          ticker_info["ticker"],
        "Название":       ticker_info.get("name", "")[:30],
        "Биржа":          ticker_info.get("exchange", ""),
        "Цена $":         round(last_price, 4),
        "Сигнал":         sig_type,
        "Пробой %":       f"+{change_pct}%" if "↑" in sig_type else f"-{change_pct}%",
        "Объём ×":        round(vol_mult, 1),
        "Дней в канале":  accum_days,
        "Канал":          f"${round(ch_min,4)} – ${round(ch_max,4)}",
        "Тело свечи %":   round(today_body, 1),
        "Опционы":        "✅" if cfg.get("options_only") else "—",
        "Сессия":         session.upper(),
        "Время":          datetime.now().strftime("%H:%M:%S"),
    }


# ── NOTIFICATIONS ───────────────────────────────────────────────

def play_sound():
    """Звуковой сигнал через системные средства."""
    try:
        if platform.system() == "Darwin":  # Mac
            subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], timeout=3)
        elif platform.system() == "Linux":
            subprocess.run(["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"], timeout=3)
        elif platform.system() == "Windows":
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception:
        pass


def send_system_notification(title, message):
    """Системное уведомление."""
    try:
        if platform.system() == "Darwin":  # Mac
            script = f'display notification "{message}" with title "{title}" sound name "Glass"'
            subprocess.run(["osascript", "-e", script], timeout=5)
        elif platform.system() == "Linux":
            subprocess.run(["notify-send", title, message], timeout=5)
        elif platform.system() == "Windows":
            # Windows Toast через PowerShell
            ps = f"""
            Add-Type -AssemblyName System.Windows.Forms
            $n = New-Object System.Windows.Forms.NotifyIcon
            $n.Icon = [System.Drawing.SystemIcons]::Information
            $n.Visible = $true
            $n.ShowBalloonTip(5000, '{title}', '{message}', [System.Windows.Forms.ToolTipIcon]::Info)
            """
            subprocess.run(["powershell", "-Command", ps], timeout=10)
    except Exception:
        pass


# ── MAIN UI ─────────────────────────────────────────────────────────

# Пример паттерна
with st.expander("📊 Как выглядит нужный паттерн", expanded=False):
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
        **Что ищем:**
        1. Акция стоит ПЛОСКО много дней (канал узкий)
        2. Объём в эти дни — низкий, тихий
        3. Последний день — РЕЗКИЙ выход вверх
        4. Объём последнего дня — в разы выше обычного
        5. Большая зелёная свеча
        """)
    with col_b:
        st.markdown("""
        **Примеры с твоих скриншотов:**
        - Акция 1: накопление у $0.0805 → пробой вверх
        - Акция 2: накопление у $0.560 → пробой вверх
        - SPHL: накопление у $1.92 → взлёт до $25 (+631%)
        """)

# Метрики
m1, m2, m3, m4 = st.columns(4)
if "auto_last_run" not in st.session_state:
    st.session_state.auto_last_run = None
if "auto_count" not in st.session_state:
    st.session_state.auto_count = 0
if "stats" not in st.session_state:
    st.session_state.stats    = {"checked": 0, "up": 0, "down": 0}
    st.session_state.results  = []

m1.metric("Проверено",      st.session_state.stats["checked"])
m2.metric("↑ Пробоев вверх", st.session_state.stats["up"])
m3.metric("↓ Пробоев вниз",  st.session_state.stats["down"])
m4.metric("Всего найдено",   len(st.session_state.results))

st.divider()

# Кнопка старта
# ── AUTO-REFRESH DISPLAY ────────────────────────────────────────
if auto_scan:
    now_ts = datetime.now()

    # Показываем таймер
    timer_col1, timer_col2, timer_col3 = st.columns(3)
    with timer_col1:
        st.info(f"⏰ Авто-поиск: каждые **{auto_interval} мин**")
    with timer_col2:
        if st.session_state.auto_last_run:
            elapsed = int((now_ts - st.session_state.auto_last_run).total_seconds() // 60)
            st.info(f"🕐 Последний запуск: **{elapsed} мин назад**")
        else:
            st.info("🕐 Ещё не запускался")
    with timer_col3:
        st.info(f"🔄 Прогонов: **{st.session_state.auto_count}**")

    # Проверяем: пора ли запускать?
    should_auto_run = False
    if st.session_state.auto_last_run is None:
        should_auto_run = True
    else:
        elapsed_sec = (now_ts - st.session_state.auto_last_run).total_seconds()
        if elapsed_sec >= auto_interval * 60:
            should_auto_run = True

    # Авто-перезагрузка страницы каждую минуту пока авто-режим включён
    st.markdown(
        f"""<meta http-equiv="refresh" content="60">""",
        unsafe_allow_html=True
    )
else:
    should_auto_run = False

st.divider()

btn_col, info_col = st.columns([1, 3])
with btn_col:
    start = st.button("🔍 Сканировать", type="primary", use_container_width=True)
with info_col:
    now = datetime.now()
    minute = now.hour * 60 + now.minute
    if 4*60 <= minute < 9*60+30:
        st.info("🌅 Pre-Market сейчас активен (4:00–9:30 ET)")
    elif 9*60+30 <= minute <= 16*60:
        st.success("🟢 Основная сессия открыта (9:30–16:00 ET)")
    elif 16*60 < minute <= 20*60:
        st.info("🌙 Post-Market сейчас активен (16:00–20:00 ET)")
    else:
        st.warning("💤 Рынок закрыт — данные по последнему закрытию")

# ── SCAN ────────────────────────────────────────────────────────
if start or (auto_scan and should_auto_run):
    strict_mode = "СТРОГИЙ" in mode
    cfg = {
        "max_price_up": max_price_up,
        "max_price_dn": max_price_dn,
        "min_days":    min_days,
        "min_vol":     min_vol,
        "channel_pct": channel_pct,
        "min_breakout": min_breakout,
        "signal_type": signal_type,
        "strict":      strict_mode,
        "options_only": options_filter,
        "sessions": [s for s, active in [("premarket", sess_premarket), ("regular", sess_regular), ("postmarket", sess_postmarket)] if active],
    }

    st.session_state.results = []
    st.session_state.stats   = {"checked": 0, "up": 0, "down": 0}

    with st.spinner("Загружаем список тикеров..."):
        all_tickers = get_tickers(exchange, max_price_up, max_price_dn)

    scan_list = all_tickers[:max_tickers]
    st.info(f"Тикеров до ${max(max_price_up,max_price_dn)}: **{len(all_tickers)}** (уже отфильтровано) | Проверяем: **{len(scan_list)}** | Режим: **{mode}**")

    progress  = st.progress(0)
    status    = st.empty()
    table_box = st.empty()

    hits = []

    sessions = cfg.get("sessions", ["regular"])
    total_ops = len(scan_list) * len(sessions)
    op = 0

    for session in sessions:
        sess_label = {"premarket": "🌅 Pre-Market", "regular": "📈 Дневная", "postmarket": "🌙 Post-Market"}[session]
        for i, t in enumerate(scan_list):
            op += 1
            progress.progress(op / total_ops)
            status.caption(f"{sess_label} | ⏳ {t['ticker']} ({i+1}/{len(scan_list)}) · найдено: {len(hits)}")

            try:
                r = analyze(t, cfg, session)
                if r:
                    hits.append(r)
                    if "↑" in r["Сигнал"]:
                        st.session_state.stats["up"] += 1
                    else:
                        st.session_state.stats["down"] += 1
                    df_show = pd.DataFrame(hits)
                    table_box.dataframe(df_show, use_container_width=True, hide_index=True)
            except Exception:
                pass

            st.session_state.stats["checked"] = op
            time.sleep(0.15)

    st.session_state.results = hits
    progress.progress(1.0)
    # ── ОПОВЕЩЕНИЯ ──────────────────────────────────────────────
    st.session_state.auto_last_run = datetime.now()
    st.session_state.auto_count += 1

    if hits:
        # Звук на компьютере
        if auto_scan and notify_sound:
            play_sound()

        # Формируем Telegram сообщение
        lines = ["📈 <b>BREAKOUT SCREENER — найдены сигналы!</b>", ""]
        for h in hits:
            icon = "🟢" if "↑" in h["Сигнал"] else "🔴"
            opt  = " | опционы ✅" if h.get("Опционы") == "✅" else ""
            lines.append(
                f"{icon} <b>{h['Тикер']}</b>  ${h['Цена $']}  {h['Пробой %']}"
                f"  | Объём ×{h['Объём ×']}"
                f"  | {h['Дней в канале']} дн.{opt}"
            )
        lines.append("")
        lines.append(f"⏰ Время: {datetime.now().strftime('%H:%M ET')}")
        lines.append(f"📊 Проверено акций: {len(scan_list)}")
        tg_message = "\n".join(lines)

        # Отправка в Telegram
        ok = send_telegram(tg_message)
        if ok:
            st.toast("📱 Уведомление отправлено в Telegram!", icon="✅")
        else:
            st.toast("⚠️ Telegram недоступен", icon="⚠️")

        # Баннер в интерфейсе
        signals_text = " | ".join([
            f"{h['Тикер']} {h['Пробой %']}" for h in hits[:5]
        ])
        st.success(f"🚨 НАЙДЕНО {len(hits)} СИГНАЛОВ: {signals_text}")

    else:
        # Если ничего не найдено — тихо, без уведомления
        if auto_scan:
            st.toast(f"Сканирование завершено — сигналов нет ({datetime.now().strftime('%H:%M')})")

    status.success(f"✅ Готово! Проверено {len(scan_list)} · Найдено сигналов: {len(hits)}")

    if hits:
        csv = pd.DataFrame(hits).to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Скачать CSV",
            data=csv,
            file_name=f"breakout_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )

elif st.session_state.results:
    st.subheader(f"Последние результаты — {len(st.session_state.results)} сигналов")
    st.dataframe(pd.DataFrame(st.session_state.results),
                 use_container_width=True, hide_index=True)
    csv = pd.DataFrame(st.session_state.results).to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Скачать CSV", data=csv,
                       file_name=f"breakout_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                       mime="text/csv")
else:
    st.info("👆 Нажми «Сканировать» для начала поиска")
