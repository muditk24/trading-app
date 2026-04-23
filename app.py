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


# ================= SET 2: SuperTrend(10,3) =================
def supertrend_bull_bear(df, period=10, mult=3.0):
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
            if c.iloc[i] < fl[i]: direction[i] = -1
            else: direction[i] = 1
        else:
            if c.iloc[i] > fu[i]: direction[i] = 1
            else: direction[i] = -1
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
        return [{"title": i.find("title").text, "link": i.find("link").text} for i in root.findall(".//item")[:3]]
    except Exception:
        return []

def get_atm_strike(price, symbol_name):
    if "NIFTY 50" in symbol_name: return round(price / 50) * 50
    if "BANK NIFTY" in symbol_name: return round(price / 100) * 100
    return round(price)

def _round_strike(x: float, symbol_name: str) -> int:
    if "NIFTY 50" in symbol_name and "BANK" not in symbol_name: return int(round(x / 50) * 50)
    if "BANK NIFTY" in symbol_name: return int(round(x / 100) * 100)
    return int(round(x))

def ladder_start_atm(spot: float, symbol_name: str, stp: int) -> int:
    sp = float(spot)
    if "BANK NIFTY" in symbol_name: return int(get_atm_strike(sp, symbol_name))
    if "NIFTY 50" in symbol_name:
        if stp >= 100: return int(round(sp / 100.0) * 100)
        return int(get_atm_strike(sp, symbol_name))
    return int(get_atm_strike(sp, symbol_name))

def set2_call_put_tables_clean(spot: float, symbol_name: str, ladder_step: int = 100, n: int = 4, s2=None):
    stp = int(ladder_step)
    atm0 = ladder_start_atm(spot, symbol_name, stp)
    ce_st = [_round_strike(atm0 + i * stp, symbol_name) for i in range(n)]
    pe_st = [_round_strike(atm0 - i * stp, symbol_name) for i in range(n)]

    def get_rec_text(is_call, i):
        if s2 is None or s2.get("n_total", 0) == 0: return "⚪ Wait"
        want = "CALL" if is_call else "PUT"
        if s2.get("side") != want: return "⚪ Avoid"
        
        gr = s2.get("grade", "SKIP")
        ok = bool(s2.get("ok"))
        n_p = s2.get("n_pass", 0)
        
        if i == 0:  # ATM
            if gr in ("STRONG", "VERY_STRONG") and ok: return f"🟢 Strong {want}"
            if gr == "MODERATE" or (n_p >= 7): return f"🟡 Weak {want}"
            return "⚪ Wait"
        elif i == 1:  # 1 OTM
            if gr == "VERY_STRONG" and ok and s2.get("vol_spike"): return f"🟢 Buy (1-OTM {want})"
            return "⚪ Avoid"
        return "⚪ Avoid"

    def r_ce(i, strike):
        return {"Strike (CE)": strike, "Recommendation": get_rec_text(True, i), "Stop Loss": "-30% Prem"}

    def r_pe(i, strike):
        return {"Strike (PE)": strike, "Recommendation": get_rec_text(False, i), "Stop Loss": "-30% Prem"}

    return {
        "calls": pd.DataFrame([r_ce(i, s) for i, s in enumerate(ce_st)]),
        "puts": pd.DataFrame([r_pe(i, s) for i, s in enumerate(pe_st)])
    }

def format_set2_recommendation_badge(s2) -> Tuple[str, str]:
    if s2 is None or "n_total" not in s2: return "⚪ SET2: — (no data)", "info"
    if s2.get("n_total", 0) == 0: return "⚪ NO CROSS / WAIT", "warning"
    side = s2.get("side", "NONE")
    gr = s2.get("grade", "SKIP")
    n_p, n_t = s2.get("n_pass", 0), s2.get("n_total", 1)
    ok = bool(s2.get("ok"))
    if side == "CALL":
        if gr in ("STRONG", "VERY_STRONG") and ok and n_p >= n_t: return f"🟢 STRONG CALL ({n_p}/{n_t} rules)", "success"
        if gr in ("STRONG", "VERY_STRONG") and not ok: return f"🟡 WEAK CALL ({n_p}/{n_t})", "warning"
        if gr == "MODERATE" or (7 <= n_p < n_t): return f"🟡 WEAK CALL ({n_p}/{n_t} rules)", "warning"
        return f"⏳ NO TRADE / WAIT ({n_p}/{n_t} rules)", "info"
    if side == "PUT":
        if gr in ("STRONG", "VERY_STRONG") and ok and n_p >= n_t: return f"🔴 STRONG PUT ({n_p}/{n_t} rules)", "error"
        if gr in ("STRONG", "VERY_STRONG") and not ok: return f"🟡 WEAK PUT ({n_p}/{n_t})", "warning"
        if gr == "MODERATE" or (7 <= n_p < n_t): return f"🟡 WEAK PUT ({n_p}/{n_t} rules)", "warning"
        return f"⏳ NO TRADE / WAIT ({n_p}/{n_t} rules)", "info"
    return "⚪ NO TRADE / SIDEWAYS", "info"

def ts_ist_to_time(ts):
    t = pd.Timestamp(ts)
    if t.tzinfo is not None: return t.tz_convert(IST).time(), t.tz_convert(IST).weekday()
    t2 = t.tz_localize(IST)
    return t2.time(), t2.weekday()

def set2_time_window_ok(bar_ts):
    t, wd = ts_ist_to_time(bar_ts)
    if wd >= 5: return False, "weekend"
    tmin = t.hour * 60 + t.minute
    o45, m1, a130, a315 = 9 * 60 + 45, 11 * 60 + 30, 13 * 60 + 30, 15 * 60 + 15
    if o45 <= tmin <= m1: return True, "morning 9:45–11:30"
    if a130 <= tmin <= a315: return True, "afternoon 1:30–3:15"
    return False, "outside window"

def set2_now_allows_entry(now_ist: datetime, skip_event: bool):
    if skip_event: return False, "event day"
    t, wd = now_ist.time(), now_ist.weekday()
    if wd >= 5: return False, "weekend"
    tmin = t.hour * 60 + t.minute
    o45, m1, a130, a315 = 9 * 60 + 45, 11 * 60 + 30, 13 * 60 + 30, 15 * 60 + 15
    if o45 <= tmin <= m1 or a130 <= tmin <= a315: return True, "OK"
    return False, "outside window"

def analyze_set2_indices(df, symbol_name: str, now_ist: Optional[datetime] = None, skip_event_day: bool = False):
    if df is None or len(df) < 30: return None
    now_ist = now_ist or datetime.now(IST)
    df = df.copy()
    df["EMA9"] = ta.trend.EMAIndicator(df["Close"], window=9).ema_indicator()
    df["EMA21"] = ta.trend.EMAIndicator(df["Close"], window=21).ema_indicator()
    df["RSI"] = ta.momentum.RSIIndicator(df["Close"], window=14).rsi()
    df["Date"] = pd.to_datetime(df.index).date
    d2 = df.copy()
    d2["TP2"] = (df["High"] + df["Low"] + df["Close"]) / 3.0
    d2["VP2"] = d2["TP2"] * d2["Volume"]
    d2["VWAP"] = d2.groupby("Date")["VP2"].transform("cumsum") / d2.groupby("Date")["Volume"].transform("cumsum")
    df["VWAP"] = d2["VWAP"]
    df["VOL_MA20"] = df["Volume"].rolling(20, min_periods=5).mean()
    df["ST_DIR"] = supertrend_bull_bear(df, 10, 3.0)

    p, p_prev = len(df) - 2, len(df) - 3
    if p_prev < 0: return None
    row, prev = df.iloc[p], df.iloc[p_prev]
    c, rsi, e9, e21 = float(row["Close"]), float(row["RSI"]) if not pd.isna(row["RSI"]) else 50.0, float(row["EMA9"]), float(row["EMA21"])
    e9p, e21p, st_dir = float(prev["EMA9"]), float(prev["EMA21"]), int(row["ST_DIR"])
    vwapv, v, vma = float(row["VWAP"]), float(row["Volume"]), float(row["VOL_MA20"]) if not pd.isna(row["VOL_MA20"]) else 0.0
    bar_ts = df.index[p]

    vol_spike = vma > 0 and v > vma * 1.4
    vol_ok = vma > 0 and v > vma
    chop = abs(e9 - e21) / c < 0.0003 if c > 0 else False
    cross_up, cross_dn = (e9 > e21) and (e9p <= e21p), (e9 < e21) and (e9p >= e21p)
    
    checks_call = {"EMA9 cross above EMA21": bool(cross_up), "Supertrend GREEN": st_dir == 1, "RSI 45–65": 45.0 <= rsi <= 65.0, "Close above VWAP": c > vwapv, "Volume > 20-bar avg": vol_ok}
    checks_put = {"EMA9 cross below EMA21": bool(cross_dn), "Supertrend RED": st_dir == -1, "RSI 35–55": 35.0 <= rsi <= 55.0, "Close below VWAP": c < vwapv, "Volume > 20-bar avg": vol_ok}
    
    t_ok, _ = set2_time_window_ok(bar_ts)
    t_now_ok, _ = set2_now_allows_entry(now_ist, skip_event_day)
    checks_time = {"Time window OK": t_ok, "Now in window": t_now_ok}
    checks_chop = {"No EMAs chop": (not chop) or bool(cross_up) or bool(cross_dn)}

    if cross_up: base = {**checks_call, **checks_time, **checks_chop}
    elif cross_dn: base = {**checks_put, **checks_time, **checks_chop}
    else: return {"ok": False, "side": "NONE", "label": "⏳ NO EMA9/21 cross", "price": round(c, 2), "rsi": round(rsi, 1), "checks": {}, "n_pass": 0, "n_total": 0, "grade": "SKIP"}

    total, passed = len(base), sum(1 for v in base.values() if v)
    is_call = bool(cross_up)
    gr = "VERY_STRONG" if (passed == total and vol_spike) or (7 <= passed < total and vol_spike and passed >= 8) else "STRONG" if passed == total else "MODERATE" if 7 <= passed < total else "SKIP"

    return {
        "ok": bool(passed >= 9 and t_ok and t_now_ok and not skip_event_day),
        "side": "CALL" if is_call else "PUT",
        "label": f"{'🟢 CALL' if is_call else '🔴 PUT'} — {passed}/{total} rules OK",
        "grade": gr, "price": round(c, 2), "rsi": round(rsi, 1), "checks": base,
        "n_pass": passed, "n_total": total, "vol_spike": vol_spike
    }

def analyze_9_candles(df, symbol_name="Stock"):
    try:
        if len(df) < 15: return None
        df = df.copy()
        df["EMA9"] = ta.trend.EMAIndicator(df["Close"], window=9).ema_indicator()
        df["EMA21"] = ta.trend.EMAIndicator(df["Close"], window=21).ema_indicator()
        df["RSI"] = ta.momentum.RSIIndicator(df["Close"], window=14).rsi()
        df["Date"] = pd.to_datetime(df.index).date
        df["TP"] = (df["High"] + df["Low"] + df["Close"]) / 3
        df["VP"] = df["TP"] * df["Volume"]
        df["VWAP"] = df.groupby("Date")["VP"].transform("cumsum") / df.groupby("Date")["Volume"].transform("cumsum")
        last_9, curr = df.tail(9), df.iloc[-1]
        price, rsi = round(curr["Close"], 2), round(curr["RSI"], 1)
        score = 0
        if (last_9["EMA9"] > last_9["EMA21"]).all(): score += 2
        elif (last_9["EMA9"] < last_9["EMA21"]).all(): score -= 2
        elif curr["EMA9"] > curr["EMA21"]: score += 1
        else: score -= 1
        if price > curr["VWAP"]: score += 1
        else: score -= 1
        if 55 < rsi < 75: score += 1
        elif 25 < rsi < 45: score -= 1
        
        signal = "🟢 STRONG CALL" if score >= 3 else "🟢 WEAK CALL" if score == 2 else "🔴 STRONG PUT" if score <= -3 else "🔴 WEAK PUT" if score == -2 else "⚪ SIDEWAYS"
        tgt, sl, opt_type = 0, 0, ""
        if "CALL" in signal: sl, tgt, opt_type = round(price * 0.993, 2), round(price * 1.015, 2), "CE"
        elif "PUT" in signal: sl, tgt, opt_type = round(price * 1.007, 2), round(price * 0.985, 2), "PE"
        
        return {"signal": signal, "score": score, "price": price, "rsi": rsi, "target": tgt, "sl": sl, "strike": f"{get_atm_strike(price, symbol_name)} {opt_type}" if opt_type else "Wait"}
    except Exception: return None


# ================= TABS =================
t1, t2, t3, t4, t5 = st.tabs(["📊 Stock Analysis", "📈 Indices (Clean)", "🎯 Recommendations", "🔥 Scanner", "📰 News"])

with t1:
    sel = st.selectbox("🔍 Analyze Specific Stock:", list(STOCK_MAP.keys()))
    df = fetch_market_data(STOCK_MAP[sel], period="3d")
    if not df.empty:
        res = analyze_9_candles(df, sel)
        if res:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Current Price", f"₹{res['price']}")
            c2.metric("Score", f"{res['score']} / 4")
            c3.markdown(f"**{res['signal']}**")
            c4.metric("RSI", res['rsi'])
            fig = go.Figure(data=[go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"])])
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig, use_container_width=True)

with t2:
    st.header("📈 Nifty & BankNifty Live SET2")
    skip_event = st.checkbox("Skip News/Event Day", value=False)
    cols = st.columns(2)
    
    for j, (name, sym) in enumerate(INDICES.items()):
        idx_df = fetch_market_data(sym, period="5d")
        with cols[j]:
            st.subheader(name)
            if not idx_df.empty:
                s2 = analyze_set2_indices(idx_df, name, skip_event_day=skip_event) if len(idx_df) >= 30 else None
                if s2:
                    s2line, s2k = format_set2_recommendation_badge(s2)
                    st.markdown(f"**{s2line}**")
                    st.metric(f"Spot Price", f"₹{s2['price']}", f"RSI: {s2['rsi']}")
                
                sp_ref = float(idx_df.iloc[-1]["Close"])
                otab = set2_call_put_tables_clean(sp_ref, name, ladder_step=100 if "BANK" in name else 50, n=4, s2=s2)
                
                st.markdown("### Call Options (CE)")
                st.dataframe(otab["calls"], use_container_width=True, hide_index=True)
                st.markdown("### Put Options (PE)")
                st.dataframe(otab["puts"], use_container_width=True, hide_index=True)

with t3:
    st.header("🎯 Active Buy Recommendations")
    if st.button("🔍 Find Setup"):
        recom_list = []
        for name, s in {**INDICES, **STOCK_MAP}.items():
            temp_df = fetch_market_data(s, period="2d")
            if not temp_df.empty:
                res = analyze_9_candles(temp_df, name)
                if res and ("STRONG" in res["signal"] or "WEAK" in res["signal"]):
                    recom_list.append({"Asset": name, "Signal": res["signal"], "Entry (Spot)": res["price"], "Target": res["target"], "SL": res["sl"]})
        if recom_list: st.dataframe(pd.DataFrame(recom_list), use_container_width=True)

with t4:
    st.header("🔥 Momentum Scanner")
    if st.button("🚀 Start Scan"):
        results = []
        for n, s in STOCK_MAP.items():
            scan_df = fetch_market_data(s, period="3d")
            if not scan_df.empty:
                r = analyze_9_candles(scan_df, n)
                if r: results.append({"Stock": n, "Signal": r["signal"], "RSI": r["rsi"], "LTP": r["price"]})
        if results: st.dataframe(pd.DataFrame(results), use_container_width=True)

with t5:
    st.header("📰 Live Stock News")
    news_sel = st.selectbox("Choose Stock:", list(STOCK_MAP.keys()))
    if st.button("Fetch News"):
        news_items = get_indian_news(news_sel)
        for item in news_items: st.markdown(f"- [{item['title']}]({item['link']})")
