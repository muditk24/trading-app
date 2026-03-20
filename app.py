import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
import numpy as np
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from nsepython import nse_quote_ltp
from datetime import datetime

# ================= UI SETUP =================
st.set_page_config(page_title="Pro 5m Options Trader", layout="wide", page_icon="📈")

# ================= MASTER STOCK LIST (NIFTY 100) =================
STOCK_MAP = {
    "RELIANCE": "RELIANCE.NS", "HDFC BANK": "HDFCBANK.NS", "ICICI BANK": "ICICIBANK.NS",
    "SBI": "SBIN.NS", "TCS": "TCS.NS", "INFOSYS": "INFY.NS", "ONGC": "ONGC.NS",
    "PFC": "PFC.NS", "COAL INDIA": "COALINDIA.NS", "GODREJ PROP": "GODREJPROP.NS",
    "TATA MOTORS": "TATAMOTORS.NS", "AXIS BANK": "AXISBANK.NS", "BHARTI AIRTEL": "BHARTIARTL.NS",
    "ZOMATO": "ZOMATO.NS", "HAL": "HAL.NS", "BEL": "BEL.NS", "ADANI ENT": "ADANIENT.NS"
}

# ================= HELPER FUNCTIONS =================
def safe_float(val, default=0):
    try: return float(val)
    except: return default

def get_indian_news(company_name):
    query = urllib.parse.quote(f'"{company_name}" share market news india when:1d')
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        return [{'title': i.find('title').text, 'link': i.find('link').text} for i in root.findall('.//item')[:2]]
    except: return []

def analyze_sentiment(headline):
    text = str(headline).lower()
    pos = ['surges', 'jumps', 'gains', 'profit', 'buy', 'wins', 'order', 'up', 'positive', 'breakout']
    neg = ['falls', 'drops', 'loss', 'sell', 'crash', 'down', 'negative', 'low', 'penalty', 'resigns']
    p_score = sum(1 for w in pos if w in text)
    n_score = sum(1 for w in neg if w in text)
    if p_score > n_score: return "🟢 Positive"
    elif n_score > p_score: return "🔴 Negative"
    return "⚪ Neutral"

# ================= TECHNICAL ENGINE (5-MIN) =================
def calculate_indicators(df):
    df = df.copy()
    close = df['Close']
    df['EMA9'] = ta.trend.EMAIndicator(close, window=9).ema_indicator()
    df['EMA21'] = ta.trend.EMAIndicator(close, window=21).ema_indicator()
    df['RSI'] = ta.momentum.RSIIndicator(close, window=14).rsi()
    # VWAP Calculation
    df['Date'] = pd.to_datetime(df.index).date
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VP'] = df['TP'] * df['Volume']
    df['CV'] = df.groupby('Date')['Volume'].cumsum()
    df['CVP'] = df.groupby('Date')['VP'].cumsum()
    df['VWAP'] = df['CVP'] / df['CV']
    # Supertrend (10, 3)
    atr = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=10).average_true_range()
    hl2 = (df['High'] + df['Low']) / 2
    df['ST_Trend'] = True 
    upper = hl2 + (3 * atr)
    lower = hl2 - (3 * atr)
    for i in range(1, len(df)):
        if df['Close'].iloc[i] > upper.iloc[i-1]: df.iloc[i, df.columns.get_loc('ST_Trend')] = True
        elif df['Close'].iloc[i] < lower.iloc[i-1]: df.iloc[i, df.columns.get_loc('ST_Trend')] = False
        else: df.iloc[i, df.columns.get_loc('ST_Trend')] = df['ST_Trend'].iloc[i-1]
    return df

def get_trade_levels(price, signal):
    """Exit Criteria: 0.8% SL and 1.6% Target (1:2 RR)"""
    if "CALL" in signal:
        sl = round(price * 0.992, 2)
        tgt = round(price + (price - sl) * 2, 2)
        exit_msg = "Exit if EMA9 < EMA21 or Price hits SL/TGT"
    else:
        sl = round(price * 1.008, 2)
        tgt = round(price - (sl - price) * 2, 2)
        exit_msg = "Exit if EMA9 > EMA21 or Price hits SL/TGT"
    return tgt, sl, exit_msg

def analyze_logic(df):
    try:
        df = calculate_indicators(df)
        l = df.iloc[-1]
        p, rsi, e9, e21, vwap, st_g = l['Close'], l['RSI'], l['EMA9'], l['EMA21'], l['VWAP'], l['ST_Trend']
        
        score = 0
        reasons = []
        if e9 > e21: score += 2; reasons.append("Bullish EMA Cross")
        else: score -= 2; reasons.append("Bearish EMA Cross")
        if p > vwap: score += 1; reasons.append("Above VWAP")
        else: score -= 1; reasons.append("Below VWAP")
        if st_g: score += 1; reasons.append("ST Green")
        else: score -= 1; reasons.append("ST Red")
        
        if score >= 2: sig = "🟢 CALL"
        elif score <= -2: sig = "🔴 PUT"
        else: sig = "⚪ NO TRADE"
        
        return sig, score, round(p,2), round(rsi,1), reasons
    except: return "⚪ ERROR", 0, 0, 0, []

# ================= APP TABS =================
st.title("🚀 AI Option Trader (5-Min Entry & Exit)")
t1, t2, t3, t4 = st.tabs(["📊 Live Analysis", "📈 Indices", "🔥 Top 10 Scanner", "📰 News & Levels"])

with t1:
    sel = st.selectbox("Select Stock:", list(STOCK_MAP.keys()))
    sym = STOCK_MAP[sel]
    
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        if st.button("🔍 Verify NSE Price"):
            st.warning(f"NSE LTP: ₹{nse_quote_ltp(sym.replace('.NS',''))}")
            
    df_5m = yf.Ticker(sym).history(period="2d", interval="5m")
    if not df_5m.empty:
        sig, sc, pr, rs, res = analyze_logic(df_5m)
        with col_v2:
            st.info(f"App Price: ₹{pr}")
            
        st.subheader(f"Current Signal: {sig}")
        if sig != "⚪ NO TRADE":
            tgt, sl, msg = get_trade_levels(pr, sig)
            c1, c2, c3 = st.columns(3)
            c1.metric("ENTRY", f"₹{pr}")
            c2.metric("TARGET (1:2)", f"₹{tgt}")
            c3.metric("STOP LOSS", f"₹{sl}")
            st.info(f"**💡 EXIT CRITERIA:** {msg}")
        
        st.write("---")
        st.subheader("📋 Technical Reasons")
        for r in res: st.write(f"✔️ {r}")
        
        fig = go.Figure(data=[go.Candlestick(x=df_5m.index, open=df_5m['Open'], high=df_5m['High'], low=df_5m['Low'], close=df_5m['Close'])])
        st.plotly_chart(fig, use_container_width=True)

with t3:
    if st.button("Start Full Market Scan 🚀"):
        results = []
        pb = st.progress(0)
        for i, (n, s) in enumerate(STOCK_MAP.items()):
            pb.progress((i+1)/len(STOCK_MAP))
            d = yf.Ticker(s).history(period="2d", interval="5m")
            if not d.empty:
                si, sc, p, r, _ = analyze_logic(d)
                if si != "⚪ NO TRADE":
                    t, s_l, _ = get_trade_levels(p, si)
                    results.append({"Stock": n, "Signal": si, "Price": p, "Target": t, "SL": s_l})
        if results: st.table(pd.DataFrame(results))

with t4:
    st.header("📰 News Sentiment + Exit Levels")
    if st.button("Fetch Today's News"):
        news_data = []
        for n in ["RELIANCE", "HDFC BANK", "SBI", "ONGC", "TCS"]:
            items = get_indian_news(n)
            d = yf.Ticker(STOCK_MAP[n]).history(period="2d", interval="5m")
            if not d.empty:
                si, sc, p, r, _ = analyze_logic(d)
                t, s_l, _ = get_trade_levels(p, si)
                for it in items:
                    news_data.append({
                        "Stock": n, "Sentiment": analyze_sentiment(it['title']),
                        "LTP": p, "Target": t, "StopLoss": s_l, "Headline": it['title']
                    })
        if news_data: st.table(pd.DataFrame(news_data))
