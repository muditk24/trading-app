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
st.title("🎯 Pro Trader Dashboard (9-Candle + ORB Indices)")

# ================= MASTER LIST =================
STOCK_MAP = {
    "RELIANCE": "RELIANCE.NS", "HDFC BANK": "HDFCBANK.NS", "ICICI BANK": "ICICIBANK.NS",
    "SBI": "SBIN.NS", "TCS": "TCS.NS", "INFOSYS": "INFY.NS", "ONGC": "ONGC.NS",
    "PFC": "PFC.NS", "COAL INDIA": "COALINDIA.NS", "TATA MOTORS": "TATAMOTORS.NS",
    "AXIS BANK": "AXISBANK.NS", "BHARTI AIRTEL": "BHARTIARTL.NS", "L&T": "LT.NS",
    "BAJAJ FINANCE": "BAJFINANCE.NS", "ITC": "ITC.NS"
}
INDICES = {"NIFTY 50": "^NSEI", "BANK NIFTY": "^NSEBANK"}


# ================= TREND: SuperTrend(10,3) =================
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
    if "NIFTY" in symbol_name: return round(price / 100) * 100
    return round(price)

def _round_strike(x: float, symbol_name: str) -> int:
    if "NIFTY" in symbol_name: return int(round(x / 100) * 100)
    return int(round(x))

def ladder_start_atm(spot: float, symbol_name: str, stp: int) -> int:
    return int(get_atm_strike(spot, symbol_name))

# ================= NEW INDICES STRATEGY (ORB + VWAP + VOL + TREND) =================
def analyze_orb_vwap_trend(df, symbol_name: str):
    if df is None or len(df) < 15: return None
    df = df.copy()
    
    df["Date"] = pd.to_datetime(df.index).date
    
    # 1. VWAP Calculation
    df["TP"] = (df["High"] + df["Low"] + df["Close"]) / 3.0
    df["VP"] = df["TP"] * df["Volume"]
    df["VWAP"] = df.groupby("Date")["VP"].transform("cumsum") / df.groupby("Date")["Volume"].transform("cumsum")
    
    # 2. Volume MA (for Volume filter)
    df["VOL_MA20"] = df["Volume"].rolling(20, min_periods=5).mean()
    
    # 3. Trend (Supertrend 10,3)
    df["ST_DIR"] = supertrend_bull_bear(df, 10, 3.0)
    
    # 4. ORB (First 15-min Opening Range Breakout = First 3 bars of 5m timeframe)
    first_3_bars = df.groupby("Date").head(3)
    orb_highs = first_3_bars.groupby("Date")["High"].max()
    orb_lows = first_3_bars.groupby("Date")["Low"].min()
    df["ORB_High"] = df["Date"].map(orb_highs)
    df["ORB_Low"] = df["Date"].map(orb_lows)

    # Fetch latest data point
    curr = df.iloc[-1]
    c = float(curr["Close"])
    vwap = float(curr["VWAP"])
    v = float(curr["Volume"])
    vma = float(curr["VOL_MA20"]) if not pd.isna(curr["VOL_MA20"]) else 0.0
    st_dir = int(curr["ST_DIR"])
    orb_h = float(curr["ORB_High"])
    orb_l = float(curr["ORB_Low"])

    # Boolean Checks
    orb_up = c > orb_h
    orb_dn = c < orb_l
    vwap_up = c > vwap
    vwap_dn = c < vwap
    vol_ok = v > vma and vma > 0
    trend_up = st_dir == 1
    trend_dn = st_dir == -1

    # Signal Logic
    strong_call = orb_up and vwap_up and vol_ok and trend_up
    strong_put = orb_dn and vwap_dn and vol_ok and trend_dn
    
    side = "NONE"
    grade = "WAIT"
    
    if strong_call:
        side = "CALL"
        grade = "STRONG"
    elif strong_put:
        side = "PUT"
        grade = "STRONG"
    elif orb_up:
        side = "CALL"
        grade = "WEAK" # Only ORB broken, lacking volume/vwap/trend support
    elif orb_dn:
        side = "PUT"
        grade = "WEAK"

    return {
        "price": round(c, 2),
        "vwap": round(vwap, 2),
        "orb_high": round(orb_h, 2),
        "orb_low": round(orb_l, 2),
        "trend_dir": "🟢 Bullish" if trend_up else "🔴 Bearish" if trend_dn else "⚪ Neutral",
        "vol_ok": vol_ok,
        "orb_up": orb_up,
        "orb_dn": orb_dn,
        "vwap_up": vwap_up,
        "vwap_dn": vwap_dn,
        "side": side,
        "grade": grade,
        "is_strong_call": strong_call,
        "is_strong_put": strong_put
    }

def indices_options_tables(spot: float, symbol_name: str, ladder_step: int = 100, n: int = 4, data=None):
    stp = int(ladder_step)
    atm0 = ladder_start_atm(spot, symbol_name, stp)
    ce_st = [_round_strike(atm0 + i * stp, symbol_name) for i in range(n)]
    pe_st = [_round_strike(atm0 - i * stp, symbol_name) for i in range(n)]

    def get_rec_text(is_call, i):
        if not data or data.get("side") == "NONE": return "⚪ Wait"
        want = "CALL" if is_call else "PUT"
        
        if data.get("side") != want: return "⚪ Avoid"
        
        if data.get("grade") == "STRONG":
            return f"🟢 Strong Buy (Focus ATM)" if i == 0 else f"🟡 Buy {want}"
        if data.get("grade") == "WEAK":
            return f"🟡 Risky/Weak {want}"
            
        return "⚪ Wait"

    return {
        "calls": pd.DataFrame([{"Strike (CE)": s, "Recommendation": get_rec_text(True, i), "Stop Loss": "-30% Prem"} for i, s in enumerate(ce_st)]),
        "puts": pd.DataFrame([{"Strike (PE)": s, "Recommendation": get_rec_text(False, i), "Stop Loss": "-30% Prem"} for i, s in enumerate(pe_st)])
    }

# Original 9 Candles function unchanged
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
t1, t2, t3, t4, t5 = st.tabs(["📊 Stock Analysis", "📈 Indices (ORB+VWAP)", "🎯 Recommendations", "🔥 Scanner", "📰 News"])

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
    st.header("📈 Nifty & BankNifty Live (ORB + Vol + VWAP + Trend)")
    cols = st.columns(2)
    
    for j, (name, sym) in enumerate(INDICES.items()):
        idx_df = fetch_market_data(sym, period="5d")
        with cols[j]:
            st.subheader(name)
            if not idx_df.empty:
                s_data = analyze_orb_vwap_trend(idx_df, name)
                if s_data:
                    # Headline Signal
                    if s_data["is_strong_call"]:
                        st.markdown("**🟢 STRONG CALL (All 4 Filters Passed)**")
                    elif s_data["is_strong_put"]:
                        st.markdown("**🔴 STRONG PUT (All 4 Filters Passed)**")
                    else:
                        st.markdown("**⏳ WAITING FOR PROPER BREAKOUT...**")
                    
                    # 4 Metrics Printout
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Spot LTP", f"₹{s_data['price']}")
                    m2.metric("VWAP", f"₹{s_data['vwap']}")
                    m3.metric("Trend (ST)", s_data["trend_dir"])
                    m4.metric("ORB Range", f"{s_data['orb_high']} - {s_data['orb_low']}")
                    
                    # Filter Checks
                    st.caption(
                        f"**Filters Check:** "
                        f"ORB Brk: {'🟢 Up' if s_data['orb_up'] else '🔴 Dn' if s_data['orb_dn'] else '⚪ Inside'} | "
                        f"Vol > Avg: {'🟢 Yes' if s_data['vol_ok'] else '🔴 No'} | "
                        f"VWAP: {'🟢 Above' if s_data['vwap_up'] else '🔴 Below'}"
                    )
                    st.write("---")
                    
                    # Options Table
                    otab = indices_options_tables(s_data['price'], name, ladder_step=100, n=4, data=s_data)
                    
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
