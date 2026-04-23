import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import time
import numpy as np
from zoneinfo import ZoneInfo
from datetime import datetime
from typing import Optional, Tuple

IST = ZoneInfo("Asia/Kolkata")

# ================= UI SETUP =================
st.set_page_config(page_title="Alpha 9-Candle Scanner", layout="wide", page_icon="🎯")
st.title("🎯 Pro Trader Dashboard (9-Candle + SET2 Indices)")

# ================= MASTER LIST =================
STOCK_MAP = {
    "RELIANCE": "RELIANCE.NS", "HDFC BANK": "HDFCBANK.NS", "ICICI BANK": "ICICIBANK.NS",
    "SBI": "SBIN.NS", "TCS": "TCS.NS", "INFOSYS": "INFY.NS", "ONGC": "ONGC.NS",
    "PFC": "PFC.NS", "COAL INDIA": "COALINDIA.NS", "TATA MOTORS": "TATAMOTORS.NS",
    "AXIS BANK": "AXISBANK.NS", "BHARTI AIRTEL": "BHARTIARTL.NS", "L&T": "LT.NS",
    "BAJAJ FINANCE": "BAJFINANCE.NS", "ITC": "ITC.NS"
}
INDICES = {"NIFTY 50": "^NSEI", "BANK NIFTY": "^NSEBANK"}


# ================= SET 2: SuperTrend(10,3) — final bands, flip on cross =================
def supertrend_bull_bear(df, period=10, mult=3.0):
    """1 = green (bull), -1 = red (bear), aligned with common ATR/HL2 SuperTrend logic (NSE 5m)."""
    d = df.copy()
    h, l, c = d["High"], d["Low"], d["Close"]
    n = len(d)
    if n < period + 2:
        return pd.Series(0, index=df.index)
    atr = ta.volatility.AverageTrueRange(h, l, c, window=period).average_true_range()
    hl2 = (h + l) / 2.0
    u0 = hl2 + mult * atr
    l0 = hl2 - mult * atr
    fu, fl = u0.to_numpy().copy(), l0.to_numpy().copy()
    for i in range(1, n):
        c_prev = c.iloc[i - 1]
        bu_i, bl_i = u0.iloc[i], l0.iloc[i]
        fup, flp = fu[i - 1], fl[i - 1]
        if np.isnan(fup) or np.isnan(flp):
            fu[i], fl[i] = bu_i, bl_i
            continue
        if bu_i < fup or c_prev > fup:
            fu[i] = bu_i
        else:
            fu[i] = fup
        if bl_i > flp or c_prev < flp:
            fl[i] = bl_i
        else:
            fl[i] = flp
    direction = np.ones(n, dtype=int)
    for i in range(1, n):
        if np.isnan(fl[i]) or np.isnan(fu[i]):
            direction[i] = direction[i - 1]
            continue
        if direction[i - 1] == 1:
            if c.iloc[i] < fl[i]:
                direction[i] = -1
            else:
                direction[i] = 1
        else:
            if c.iloc[i] > fu[i]:
                direction[i] = 1
            else:
                direction[i] = -1
    return pd.Series(direction, index=df.index)


# ================= HELPER FUNCTIONS =================
@st.cache_data(ttl=60, show_spinner=False)
def fetch_market_data(symbol, period="2d"):
    try:
        time.sleep(0.5)
        df = yf.Ticker(symbol).history(period=period, interval="5m")
        return df
    except Exception:
        return pd.DataFrame()


def get_indian_news(company_name):
    query = urllib.parse.quote(f'"{company_name}" share market news india when:1d')
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        return [
            {"title": i.find("title").text, "link": i.find("link").text}
            for i in root.findall(".//item")[:3]
        ]
    except Exception:
        return []


def get_atm_strike(price, symbol_name):
    if "NIFTY 50" in symbol_name:
        return round(price / 50) * 50
    if "BANK NIFTY" in symbol_name:
        return round(price / 100) * 100
    return round(price)


def step_for_symbol(symbol_name):
    return 100 if "BANK NIFTY" in symbol_name else 50 if "NIFTY" in symbol_name else 1


def _round_strike(x: float, symbol_name: str) -> int:
    if "NIFTY 50" in symbol_name and "BANK" not in symbol_name:
        return int(round(x / 50) * 50)
    if "BANK NIFTY" in symbol_name:
        return int(round(x / 100) * 100)
    return int(round(x))


def ladder_start_atm(spot: float, symbol_name: str, stp: int) -> int:
    """
    ATM anchor for 5+5 ladder.
    NIFTY: index options are 50-wide, but NSE/chain UI often centres on **nearest 100** to spot
    when you show 100-pt step ladders (24200, 24300, …) — we match that.
    BANKNIFTY: exchange step 100 — same as get_atm_strike.
    """
    sp = float(spot)
    if "BANK NIFTY" in symbol_name:
        return int(get_atm_strike(sp, symbol_name))
    if "NIFTY 50" in symbol_name:
        if stp >= 100:
            return int(round(sp / 100.0) * 100)
        return int(get_atm_strike(sp, symbol_name))
    return int(get_atm_strike(sp, symbol_name))


def _ladder_rec_qty_targets(is_call: bool, row_i: int, s2) -> Tuple[str, int, int, int, int, int]:
    """
    Per strike row: (recommendation, qty, SL%, T1%, T2%, T3%) — short tags, no long reason text.
    SET2: SL -30% prem; T 30/50/80% prem. Qty 0/1 (rulebook: max 2 trades/day = user session).
    """
    sl, t1, t2, t3 = 30, 30, 50, 80
    if s2 is None or s2.get("n_total", 0) == 0:
        return "WAIT", 0, sl, t1, t2, t3
    sd = s2.get("side", "NONE")
    if sd not in ("CALL", "PUT"):
        return "WAIT", 0, sl, t1, t2, t3
    want = "CALL" if is_call else "PUT"
    if sd != want:
        return ("USE_PE" if is_call else "USE_CE"), 0, sl, t1, t2, t3
    gr = s2.get("grade", "SKIP")
    n_p, n_t = s2.get("n_pass", 0), s2.get("n_total", 1)
    ok = bool(s2.get("ok"))
    vq = bool(s2.get("vol_spike"))
    if row_i == 0:
        if ok and n_p >= n_t and gr in ("STRONG", "VERY_STRONG"):
            return "TRADE", 1, sl, t1, t2, t3
        if gr == "MODERATE" and n_p >= 7 and ok:
            return "TRADE_S", 1, sl, t1, t2, t3
        if n_p < 7 or not ok:
            return "WAIT", 0, sl, t1, t2, t3
        if gr in ("STRONG", "VERY_STRONG", "MODERATE"):
            return "TRADE", 1, sl, t1, t2, t3
        return "WAIT", 0, sl, t1, t2, t3
    if row_i == 1:
        if gr == "VERY_STRONG" and vq and ok:
            return "TRADE_1OTM", 1, sl, t1, t2, t3
        return "SKIP_1OTM", 0, sl, t1, t2, t3
    return "SKIP_DEEP", 0, sl, t1, t2, t3


def set2_five_call_put_tables(
    spot: float, symbol_name: str, ladder_step: int = 100, n: int = 5, s2=None
):
    """5 CE + 5 PE: Recommendation + Qty + SL/Tgt % (numbers). Optional s2 for side/grade match."""
    stp = int(ladder_step)
    atm0 = ladder_start_atm(spot, symbol_name, stp)
    ce_st = [_round_strike(atm0 + i * stp, symbol_name) for i in range(n)]
    pe_st = [_round_strike(atm0 - i * stp, symbol_name) for i in range(n)]

    def r_ce(i, strike):
        rec, qty, sl_p, t1, t2, t3 = _ladder_rec_qty_targets(True, i, s2)
        return {
            "S.No": i + 1,
            "Strike (CE)": strike,
            "Recommendation": rec,
            "Qty": qty,
            "SL %": sl_p,
            "Tgt1 %": t1,
            "Tgt2 %": t2,
            "Tgt3 %": t3,
        }

    def r_pe(i, strike):
        rec, qty, sl_p, t1, t2, t3 = _ladder_rec_qty_targets(False, i, s2)
        return {
            "S.No": i + 1,
            "Strike (PE)": strike,
            "Recommendation": rec,
            "Qty": qty,
            "SL %": sl_p,
            "Tgt1 %": t1,
            "Tgt2 %": t2,
            "Tgt3 %": t3,
        }

    return {
        "atm": atm0,
        "spot": round(float(spot), 2),
        "calls": pd.DataFrame([r_ce(i, s) for i, s in enumerate(ce_st)]),
        "puts": pd.DataFrame([r_pe(i, s) for i, s in enumerate(pe_st)]),
        "step": stp,
    }


def format_set2_recommendation_badge(s2) -> Tuple[str, str]:
    """
    Return (line, ui_kind) where ui_kind in success, warning, error, info
    for STRONG/WEAK CALL/PUT / NO TRADE style wording.
    """
    if s2 is None or "n_total" not in s2:
        return "⚪ SET2: — (no data)", "info"
    if s2.get("n_total", 0) == 0:
        return "⚪ SET2: NO CROSS / WAIT (need EMA9-21 cross on last closed 5m)", "warning"
    side = s2.get("side", "NONE")
    gr = s2.get("grade", "SKIP")
    n_p, n_t = s2.get("n_pass", 0), s2.get("n_total", 1)
    ok = bool(s2.get("ok"))
    if side == "CALL":
        if gr in ("STRONG", "VERY_STRONG") and ok and n_p >= n_t:
            return f"🟢 SET2: STRONG CALL ({n_p}/{n_t} rules)", "success"
        if gr in ("STRONG", "VERY_STRONG") and not ok:
            return f"🟡 SET2: WEAK CALL — setup strong but time/window/check failed ({n_p}/{n_t})", "warning"
        if gr == "MODERATE" or (7 <= n_p < n_t):
            return f"🟡 SET2: WEAK CALL (Wait for setup) — {n_p}/{n_t} rules", "warning"
        return f"⏳ SET2: NO TRADE / WAIT (CALL) — {n_p}/{n_t} rules", "info"
    if side == "PUT":
        if gr in ("STRONG", "VERY_STRONG") and ok and n_p >= n_t:
            return f"🔴 SET2: STRONG PUT ({n_p}/{n_t} rules)", "error"
        if gr in ("STRONG", "VERY_STRONG") and not ok:
            return f"🟡 SET2: WEAK PUT — time/window failed ({n_p}/{n_t})", "warning"
        if gr == "MODERATE" or (7 <= n_p < n_t):
            return f"🟡 SET2: WEAK PUT (Wait for setup) — {n_p}/{n_t} rules", "warning"
        return f"⏳ SET2: NO TRADE / WAIT (PUT) — {n_p}/{n_t} rules", "info"
    return "⚪ SET2: NO TRADE / SIDEWAYS", "info"


def ts_ist_to_time(ts):
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        return t.tz_convert(IST).time(), t.tz_convert(IST).weekday()
    t2 = t.tz_localize(IST)
    return t2.time(), t2.weekday()


def set2_time_window_ok(bar_ts):
    t, wd = ts_ist_to_time(bar_ts)
    if wd >= 5:
        return False, "weekend (no session)"
    tmin = t.hour * 60 + t.minute
    o15 = 9 * 60 + 15
    o45 = 9 * 60 + 45
    m1 = 11 * 60 + 30
    a130 = 13 * 60 + 30
    a315 = 15 * 60 + 15
    if o15 <= tmin < 9 * 60 + 30:
        return False, "9:15–9:30 opening (first 15 min) — skip"
    if 9 * 60 + 30 <= tmin < o45:
        return False, "9:30–9:45 — use checklist from 9:45 only"
    if o45 <= tmin <= m1:
        return True, "morning window 9:45–11:30 IST (bar)"
    if m1 < tmin < a130:
        return False, "11:30–1:30 midday — avoid"
    if a130 <= tmin <= a315:
        return True, "afternoon window 1:30–3:15 IST (bar)"
    return False, "outside 9:45–11:30 or 1:30–3:15 IST (bar end)"


def set2_now_allows_entry(now_ist: datetime, skip_event: bool):
    if skip_event:
        return False, "event/news day (manual) — no trade"
    t, wd = now_ist.time(), now_ist.weekday()
    if wd >= 5:
        return False, "weekend"
    tmin = t.hour * 60 + t.minute
    o45, m1, a130, a315 = 9 * 60 + 45, 11 * 60 + 30, 13 * 60 + 30, 15 * 60 + 15
    if 9 * 60 + 15 <= tmin < 9 * 60 + 30:
        return False, "9:15–9:30 opening"
    if 9 * 60 + 30 <= tmin < o45:
        return False, "before 9:45"
    if m1 < tmin < a130:
        return False, "midday 11:30–1:30"
    if o45 <= tmin <= m1 or a130 <= tmin <= a315:
        return True, "OK (now in SET2 entry window — IST)"
    return False, "after 3:15 or before valid window"


# ================= SET 2 — Indices only =================
def analyze_set2_indices(
    df, symbol_name: str, now_ist: Optional[datetime] = None, skip_event_day: bool = False
):
    if df is None or len(df) < 30:
        return None
    now_ist = now_ist or datetime.now(IST)
    df = df.copy()
    df["EMA9"] = ta.trend.EMAIndicator(df["Close"], window=9).ema_indicator()
    df["EMA21"] = ta.trend.EMAIndicator(df["Close"], window=21).ema_indicator()
    df["RSI"] = ta.momentum.RSIIndicator(df["Close"], window=14).rsi()
    df["Date"] = pd.to_datetime(df.index).date
    d2 = df.copy()
    d2["TP2"] = (df["High"] + df["Low"] + df["Close"]) / 3.0
    d2["VP2"] = d2["TP2"] * d2["Volume"]
    d2["VWAP"] = d2.groupby("Date")["VP2"].transform("cumsum") / d2.groupby("Date")[
        "Volume"
    ].transform("cumsum")
    df["VWAP"] = d2["VWAP"]
    df["VOL_MA20"] = df["Volume"].rolling(20, min_periods=5).mean()
    df["ST_DIR"] = supertrend_bull_bear(df, 10, 3.0)

    p = len(df) - 2
    p_prev = p - 1
    if p_prev < 0:
        return None

    row, prev = df.iloc[p], df.iloc[p_prev]
    c = float(row["Close"])
    rsi = float(row["RSI"]) if not pd.isna(row["RSI"]) else 50.0
    e9, e21 = float(row["EMA9"]), float(row["EMA21"])
    e9p, e21p = float(prev["EMA9"]), float(prev["EMA21"])
    st_dir = int(row["ST_DIR"])
    vwapv = float(row["VWAP"])
    v = float(row["Volume"])
    vma = float(row["VOL_MA20"]) if not pd.isna(row["VOL_MA20"]) else 0.0
    bar_ts = df.index[p]

    vol_spike = vma > 0 and v > vma * 1.4
    vol_ok = vma > 0 and v > vma
    chop = abs(e9 - e21) / c < 0.0003 if c > 0 else False
    cross_up = (e9 > e21) and (e9p <= e21p)
    cross_dn = (e9 < e21) and (e9p >= e21p)
    st_green = st_dir == 1
    st_red = st_dir == -1

    checks_call = {
        "EMA9 cross above EMA21 (on closed 5m)": bool(cross_up),
        "Candle closed: last full 5m (not in-progress)": True,
        "Supertrend GREEN (10,3)": st_green,
        "RSI 45–65 (CALL)": 45.0 <= rsi <= 65.0,
        "RSI < 70 (not extended)": rsi < 70.0,
        "Close above VWAP": c > vwapv and not (np.isnan(vwapv) or pd.isna(vwapv)),
        "Volume > 20-bar avg (entry candle)": vol_ok,
    }
    checks_put = {
        "EMA9 cross below EMA21 (on closed 5m)": bool(cross_dn),
        "Candle closed: last full 5m (not in-progress)": True,
        "Supertrend RED (10,3)": st_red,
        "RSI 35–55 (PUT)": 35.0 <= rsi <= 55.0,
        "RSI > 30 (not oversold for put)": rsi > 30.0,
        "Close below VWAP": c < vwapv and not (np.isnan(vwapv) or pd.isna(vwapv)),
        "Volume > 20-bar avg (entry candle)": vol_ok,
    }
    t_ok, t_note = set2_time_window_ok(bar_ts)
    t_now_ok, t_now_msg = set2_now_allows_entry(now_ist, skip_event_day)
    checks_time = {
        f"Bar in time window 9:45–11:30 or 1:30–3:15 IST — {t_note}": t_ok,
        f"Now in window (live) & not event — {t_now_msg}": t_now_ok,
    }
    checks_chop = {
        "Chop: EMAs not flat/tangled (if tangled, skip)": (not chop) or bool(cross_up) or bool(cross_dn)
    }

    if cross_up:
        base = {**checks_call, **checks_time, **checks_chop}
    elif cross_dn:
        base = {**checks_put, **checks_time, **checks_chop}
    else:
        return {
            "ok": False,
            "side": "NONE",
            "label": "⏳ NO EMA9/21 cross on last closed 5m (SET2 needs cross + Supertrend + filters)",
            "price": round(c, 2),
            "rsi": round(rsi, 1),
            "bar_time_ist": str(ts_ist_to_time(bar_ts)[0]),
            "checks": {
                "EMA cross (CALL)": bool(cross_up),
                "EMA cross (PUT)": bool(cross_dn),
                **checks_time,
                **checks_chop,
            },
            "n_pass": 0,
            "n_total": 0,
            "grade": "SKIP",
            "strike_hint": "—",
            "expiry_hint": "0DTE / 1DTE (rule); never 0DTE+deep OTM",
        }

    total = len(base)
    passed = sum(1 for v in base.values() if v)
    is_call = bool(cross_up)

    if passed == total and vol_spike:
        gr = "VERY_STRONG"
    elif passed == total:
        gr = "STRONG"
    elif 7 <= passed < total and vol_spike and passed >= 8:
        gr = "VERY_STRONG"
    elif 7 <= passed < total:
        gr = "MODERATE"
    else:
        gr = "SKIP"

    step = step_for_symbol(symbol_name)
    atm = get_atm_strike(c, symbol_name)
    opt = "CE" if is_call else "PE"
    itm1 = atm - step if opt == "CE" else atm + step
    otm1 = atm + step if opt == "CE" else atm - step
    if gr == "VERY_STRONG" and vol_spike:
        strike_hint = f"{atm} ({opt}) or {otm1} (1 OTM) — very strong + volume (SET2)"
    elif gr in ("STRONG", "VERY_STRONG"):
        strike_hint = f"{atm} ({opt}) — ATM primary (SET2)"
    elif gr == "MODERATE":
        strike_hint = f"{itm1} or {atm} (slight ITM / ATM) — 7–8 rules; size down"
    else:
        strike_hint = "DO NOT TRADE (<7 checks or time/event fail)"

    if passed < 7 or (not t_ok) or (not t_now_ok) or skip_event_day:
        label = f"⏳ SKIP / WAIT — {passed}/{total} rules OK. Need time windows + 7+ checks per SET2."
    elif 7 <= passed < total:
        label = f"🟡 MODERATE {('CALL' if is_call else 'PUT')} — {passed}/{total}; reduce size, Slight ITM/ATM"
    else:
        label = f"{'🟢 SET2 CALL' if is_call else '🔴 SET2 PUT'} — {passed}/{total} rules OK"

    return {
        "ok": bool(passed >= 9 and t_ok and t_now_ok and not skip_event_day),
        "side": "CALL" if is_call else "PUT",
        "label": label,
        "grade": gr,
        "price": round(c, 2),
        "rsi": round(rsi, 1),
        "bar_time_ist": str(ts_ist_to_time(bar_ts)[0]),
        "checks": base,
        "n_pass": passed,
        "n_total": total,
        "vol_spike": vol_spike,
        "strike_hint": strike_hint,
        "expiry_hint": "0DTE only with ATM + morning; else 1DTE. Never 0DTE+deep OTM (rulebook).",
    }


# ================= CORE LOGIC: 9-CANDLE SCANNER (stocks) =================
def analyze_9_candles(df, symbol_name="Stock"):
    try:
        if len(df) < 15:
            return None
        df = df.copy()
        df["EMA9"] = ta.trend.EMAIndicator(df["Close"], window=9).ema_indicator()
        df["EMA21"] = ta.trend.EMAIndicator(df["Close"], window=21).ema_indicator()
        df["RSI"] = ta.momentum.RSIIndicator(df["Close"], window=14).rsi()
        df["Date"] = pd.to_datetime(df.index).date
        df["TP"] = (df["High"] + df["Low"] + df["Close"]) / 3
        df["VP"] = df["TP"] * df["Volume"]
        df["VWAP"] = (
            df.groupby("Date")["VP"].transform("cumsum")
            / df.groupby("Date")["Volume"].transform("cumsum")
        )
        last_9 = df.tail(9)
        curr = df.iloc[-1]
        price = round(curr["Close"], 2)
        rsi = round(curr["RSI"], 1)
        score = 0
        reasons = []
        if (last_9["EMA9"] > last_9["EMA21"]).all():
            score += 2
            reasons.append("🟢 Strong Bullish Trend (EMA9 > EMA21)")
        elif (last_9["EMA9"] < last_9["EMA21"]).all():
            score -= 2
            reasons.append("🔴 Strong Bearish Trend (EMA9 < EMA21)")
        elif curr["EMA9"] > curr["EMA21"]:
            score += 1
            reasons.append("🟢 Fresh Bullish EMA Crossover")
        else:
            score -= 1
            reasons.append("🔴 Fresh Bearish EMA Crossover")
        if price > curr["VWAP"]:
            score += 1
            reasons.append("🟢 Price is sustaining Above VWAP")
        else:
            score -= 1
            reasons.append("🔴 Price is Below VWAP")
        if 55 < rsi < 75:
            score += 1
            reasons.append(f"🟢 Good Bullish Momentum (RSI: {rsi})")
        elif 25 < rsi < 45:
            score -= 1
            reasons.append(f"🔴 Good Bearish Momentum (RSI: {rsi})")
        else:
            reasons.append(f"⚪ RSI is Sideways/Overbought/Oversold (RSI: {rsi})")
        signal = "⚪ NO TRADE / SIDEWAYS"
        if score >= 3:
            signal = "🟢 STRONG CALL"
        elif score == 2:
            signal = "🟢 WEAK CALL (Wait for Setup)"
        elif score <= -3:
            signal = "🔴 STRONG PUT"
        elif score == -2:
            signal = "🔴 WEAK PUT (Wait for Setup)"
        tgt = sl = 0
        opt_type = ""
        atm_strike = get_atm_strike(price, symbol_name)
        if "CALL" in signal:
            sl = round(price * 0.993, 2)
            tgt = round(price * 1.015, 2)
            opt_type = "CE"
        elif "PUT" in signal:
            sl = round(price * 1.007, 2)
            tgt = round(price * 0.985, 2)
            opt_type = "PE"
        strike_str = f"{atm_strike} {opt_type}" if opt_type else "Wait for Trend"
        return {
            "signal": signal,
            "score": score,
            "price": price,
            "rsi": rsi,
            "target": tgt,
            "sl": sl,
            "reasons": reasons,
            "strike": strike_str,
        }
    except Exception:
        return None


# ================= TABS =================
t1, t2, t3, t4, t5 = st.tabs(
    ["📊 Stock Analysis", "📈 Indices (SET2)", "🎯 Recommended Calls/Puts", "🔥 Scanner", "📰 Live News"]
)

# --- TAB 1: STOCK ---
with t1:
    sel = st.selectbox("🔍 Analyze Specific Stock:", list(STOCK_MAP.keys()))
    df = fetch_market_data(STOCK_MAP[sel], period="3d")
    if not df.empty:
        res = analyze_9_candles(df, sel)
        if res:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Current Price", f"₹{res['price']}")
            c2.metric("Setup Score", f"{res['score']} / 4")
            if "CALL" in res["signal"]:
                c3.success(res["signal"])
            elif "PUT" in res["signal"]:
                c3.error(res["signal"])
            else:
                c3.warning(res["signal"])
            c4.metric("RSI", res["rsi"])
            if "TRADE" not in res["signal"]:
                st.info(f"**🎯 EXIT STRATEGY:** Target: **₹{res['target']}** | Stop Loss: **₹{res['sl']}**")
            st.write("---")
            c_chart, c_reasons = st.columns([2, 1])
            with c_chart:
                fig = go.Figure(
                    data=[
                        go.Candlestick(
                            x=df.index,
                            open=df["Open"],
                            high=df["High"],
                            low=df["Low"],
                            close=df["Close"],
                        )
                    ]
                )
                fig.update_layout(
                    height=400, margin=dict(l=0, r=0, t=30, b=0), title="5-Minute Chart"
                )
                st.plotly_chart(fig, use_container_width=True)
            with c_reasons:
                st.subheader("🧠 Setup Reasoning")
                for r in res["reasons"]:
                    st.write(r)

# --- TAB 2: INDICES SET2 ---
with t2:
    st.header("📈 Nifty & BankNifty — SET2 (EMA9/21 + Supertrend(10,3) + RSI14 + VWAP + Vol)")
    skip_event = st.checkbox("Today = news/CPI style day (no trades per SET2)", value=False)
    st.caption(
        "Entry rules use **last completed 5m** bar. Time = **IST** (9:45–11:30 & 1:30–3:15). "
        "Exits: track **option premium** (+30% / +50% / SL −30%); 30m max; rules in expander below."
    )
    cols = st.columns(2)
    for j, (name, sym) in enumerate(INDICES.items()):
        idx_df = fetch_market_data(sym, period="5d")
        with cols[j]:
            st.subheader(name)
            if idx_df is None or idx_df.empty:
                st.warning("No 5m data. Try after market or refresh.")
            else:
                st.caption("**9-candle** = same STRONG/WEAK CALL/PUT as stock tab | **SET2** = EMA+ST+RSI+VWAP+vol+time")
                res9 = analyze_9_candles(idx_df, name) if len(idx_df) >= 15 else None
                if res9:
                    a1, a2, a3, a4 = st.columns(4)
                    a1.metric("LTP (9c)", f"₹{res9['price']}")
                    a2.metric("9-candle score", f"{res9['score']}/4")
                    with a3:
                        s9 = res9["signal"]
                        if "STRONG" in s9 and "CALL" in s9:
                            st.success(s9)
                        elif "WEAK" in s9 and "CALL" in s9:
                            st.warning(s9)
                        elif "STRONG" in s9 and "PUT" in s9:
                            st.error(s9)
                        elif "WEAK" in s9 and "PUT" in s9:
                            st.warning(s9)
                        else:
                            st.info(s9)
                    a4.metric("RSI", res9["rsi"])
                    st.caption(
                        f"9-candle ref: **{res9['strike']}** | Tgt ~₹{res9['target']} | SL ~₹{res9['sl']} (spot, not option premium)"
                    )
                    with st.expander("9-candle — why (Nifty / BN)"):
                        for _r in res9["reasons"]:
                            st.write(_r)
                else:
                    st.caption("9-candle: **15+** 5m bars chahiye STRONG/WEAK dikhane ke liye.")
                st.markdown("**SET2 recommendation (rulebook style)**")
                if len(idx_df) < 30:
                    st.warning("Not enough 5m bars for full SET2 scan (need ≥30). Ladder table still from last close.")
                s2 = None
                if len(idx_df) >= 30:
                    s2 = analyze_set2_indices(idx_df, name, skip_event_day=skip_event)
                if s2 is not None:
                    s2line, s2k = format_set2_recommendation_badge(s2)
                    if s2k == "success":
                        st.success(s2line)
                    elif s2k == "warning":
                        st.warning(s2line)
                    elif s2k == "error":
                        st.error(s2line)
                    else:
                        st.info(s2line)
                if s2 and "checks" in s2 and s2.get("n_total", 0) > 0:
                    st.metric("Spot (SET2 bar)", f"₹{s2['price']}", f"RSI {s2['rsi']}")
                    st.caption(s2.get("label", "—"))
                    st.write(f"**Bar time (IST):** {s2.get('bar_time_ist', '—')}")
                    st.write(f"**Checks passed:** {s2['n_pass']}/{s2['n_total']}  |  **Grade:** {s2.get('grade', '—')}")
                    st.write(f"**Strike hint:** {s2.get('strike_hint', '—')}")
                    st.caption(s2.get("expiry_hint", ""))
                    with st.expander("9-check list (this bar + live window)"):
                        for k, v in s2["checks"].items():
                            st.write(f"{'✅' if v else '⛔'} {k}")
                    with st.expander("SET2 — Exit & risk (reference)"):
                        st.markdown(
                            """
- **Profit:** +30% premium → book 50%; +50% → full exit; +80% only if Supertrend still in favour and RSI in range.  
- **Stop:** −30% premium hard exit; **Supertrend** flip; **EMA9** crosses back; **RSI** danger (>70 on call / <30 on put).  
- **Time:** no move 2×5m bars → out; max hold 30m; end-of-window 11:30 / 3:15 style — avoid chop.  
- **Risk:** max 2 trades/day; 1–2% risk; stop after 2 losses. *Premium rules apply; spot targets are not substitute.*
"""
                        )
                elif s2 and s2.get("n_total", 0) == 0 and "checks" in s2:
                    st.write(s2.get("label", "—"))
                sp_ref = float(idx_df.iloc[-1]["Close"])
                lstep = 100
                otab = set2_five_call_put_tables(
                    sp_ref, name, ladder_step=lstep, n=5, s2=s2 if len(idx_df) >= 30 else None
                )
                st.divider()
                st.subheader("5 CALL + 5 PUT — recommendation · qty · SL/Tgt (%) per strike")
                st.caption(
                    f"LTP ₹{otab['spot']}  |  anchor {otab['atm']}  |  {lstep}pt. "
                    "**SL / Tgt%** = on **premium** (not spot). **Qty** 0/1. **Recommendation** = SET2 + SET2 ladder rules (short code)."
                )
                tc, tp = st.columns(2, gap="medium")
                with tc:
                    st.markdown("**5 CALL (CE)**")
                    st.dataframe(otab["calls"], use_container_width=True, height=320)
                with tp:
                    st.markdown("**5 PUT (PE)**")
                    st.dataframe(otab["puts"], use_container_width=True, height=320)

# --- TAB 3 ---
with t3:
    st.header("🎯 Active Buy Recommendations")
    st.write("Showing 'Strong' Call and Put signals (9-candle logic, not full SET2).")
    if st.button("🔍 Find Setup"):
        recom_list = []
        with st.spinner("Checking setups..."):
            for name, s in {**INDICES, **STOCK_MAP}.items():
                temp_df = fetch_market_data(s, period="2d")
                if not temp_df.empty:
                    res = analyze_9_candles(temp_df, name)
                    if res and ("STRONG" in res["signal"] or "WEAK" in res["signal"]):
                        recom_list.append(
                            {
                                "Asset": name,
                                "Signal": res["signal"],
                                "Strike/Action": res["strike"],
                                "Entry (Spot)": res["price"],
                                "Target": res["target"],
                                "Stop Loss": res["sl"],
                                "Score": res["score"],
                            }
                        )
        if recom_list:
            st.dataframe(
                pd.DataFrame(recom_list)
                .style.map(
                    lambda x: "background-color: #d4edda"
                    if "CALL" in str(x)
                    else ("background-color: #f8d7da" if "PUT" in str(x) else ""),
                    subset=["Signal"],
                ),
                use_container_width=True,
            )
        else:
            st.info("No active Calls/Puts right now (9-candle).")

# --- TAB 4 ---
with t4:
    st.header("🔥 Top Momentum Scanner (9-candle)")
    if st.button("🚀 Start Market Scan"):
        results = []
        pb = st.progress(0)
        items = list(STOCK_MAP.items())
        for i, (n, s) in enumerate(items):
            pb.progress((i + 1) / len(items))
            scan_df = fetch_market_data(s, period="3d")
            if not scan_df.empty:
                r = analyze_9_candles(scan_df, n)
                if r:
                    results.append(
                        {
                            "Stock": n,
                            "Signal": r["signal"],
                            "Score": r["score"],
                            "RSI": r["rsi"],
                            "LTP": r["price"],
                            "Target": r["target"],
                            "SL": r["sl"],
                        }
                    )
        if results:
            res_df = pd.DataFrame(results)
            res_df["AbsScore"] = res_df["Score"].abs()
            res_df = res_df.sort_values(
                by=["AbsScore", "RSI"], ascending=[False, False]
            ).drop(columns=["AbsScore"])
            st.dataframe(
                res_df.style.map(
                    lambda x: "color: green"
                    if "CALL" in str(x)
                    else ("color: red" if "PUT" in str(x) else ""),
                    subset=["Signal"],
                ),
                use_container_width=True,
            )

# --- TAB 5 ---
with t5:
    st.header("📰 Live Stock News")
    news_sel = st.selectbox("🗞️ Choose Stock for News:", list(STOCK_MAP.keys()))
    if st.button("Fetch Latest News"):
        with st.spinner(f"Fetching news for {news_sel}..."):
            news_items = get_indian_news(news_sel)
            if news_items:
                for item in news_items:
                    st.success(f"📌 {item['title']}")
                    st.caption(f"[Read full article here]({item['link']})")
            else:
                st.warning(f"No fresh news for {news_sel} (24h).")
