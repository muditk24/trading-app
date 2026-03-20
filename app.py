import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
import numpy as np
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from nsetools import Nse
from datetime import datetime

# NSE instance initialize karna
nse = Nse()

# ================= UI SETUP =================
st.set_page_config(page_title="Pro 5m Options Trader", layout="wide", page_icon="📈")

# ================= MASTER STOCK LIST =================
STOCK_MAP = {
    "RELIANCE": "RELIANCE.NS", "HDFC BANK": "HDFCBANK.NS", "ICICI BANK": "ICICIBANK.NS",
    "SBI": "SBIN.NS", "TCS": "TCS.NS", "INFOSYS": "INFY.NS", "ONGC": "ONGC.NS",
    "PFC": "PFC.NS", "COAL INDIA": "COALINDIA.NS", "GODREJ PROP": "GODREJPROP.NS",
    "TATA MOTORS": "TATAMOTORS.NS", "AXIS BANK": "AXISBANK.NS", "BHARTI AIRTEL": "BHARTIARTL.NS"
}

# ================= SAFE PRICE FETCH (FIX FOR KEYERROR) =================
def get_stable_nse_price(symbol):
    """Stable NSE Price fetcher with Error Handling"""
    try:
        clean_symbol = symbol.replace(".NS", "")
        data = nse.get_quote(clean_symbol)
        if data and 'lastPrice' in data:
            return data['lastPrice']
        else:
            return "Not Available"
    except Exception as e:
        return "NSE Server Busy"

# ================= HELPER FUNCTIONS =================
def analyze_sentiment(headline):
    text = str(headline).lower()
    pos = ['surges', 'jumps', 'gains', 'profit', 'buy', 'wins', 'order', 'up', 'positive']
    neg = ['falls', 'drops', 'loss', 'sell', 'crash', 'down', 'negative', 'low', 'penalty']
    if sum(1 for w in pos if w in text) > sum(1 for w in neg if w in text): return "🟢 Positive"
    elif sum(1 for w in neg if w in text) > sum(1 for w in pos if w in text): return "🔴 Negative"
    return "⚪ Neutral"

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

# ================= TECHNICAL INDICATORS =================
def calculate_indicators(df):
    df = df.copy()
    close = df['Close']
    df['EMA9'] = ta.trend.EMAIndicator(close, window=9).ema_indicator()
    df['EMA21'] = ta.trend.EMAIndicator(close, window=21).ema_indicator()
    df['RSI'] = ta.momentum.RSIIndicator(close, window=14).rsi()
    # VWAP
    df['Date'] = pd.to_datetime(df.index).date
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VP'] = df['TP'] * df['Volume']
    df['CV'] = df.groupby('Date')['Volume'].cumsum()
    df['CVP'] = df.groupby('Date')['VP'].cumsum()
    df['VWAP'] = df['CVP'] / df['CV']
    # Supertrend
    atr = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=10).average_true_range()
    hl2 = (df['High'] + df['Low']) / 2
    df['ST_Upper'] = hl2 + (3 * atr)
    df['ST_Lower'] = hl2 - (3 * atr)
    df['ST_Trend'] = True
    for i in range(1, len(df)):
        if df['Close'].iloc[i] > df['ST_Upper'].iloc[i-1]: df.iloc[i, df.columns.get_loc('ST_Trend')] = True
        elif df['Close'].iloc[i] < df['ST_Lower'].iloc[i-1]: df.iloc[i, df.columns.get_loc('ST_Trend')] = False
        else: df.iloc[i, df.columns.get_loc('ST_Trend')] = df['ST_Trend'].iloc[i-1]
    return df

def get_exit_levels(price, signal):
    if "CALL" in signal:
        sl = round(price * 0.992, 2)
        tgt = round(price + (price - sl) * 2, 2)
        msg = "Exit if EMA9 crosses below EMA21"
    else:
        sl = round(price * 1.008, 2)
        tgt = round(price - (sl - price) * 2, 2)
        msg = "Exit if EMA9 crosses above EMA21"
    return tgt, sl, msg

# ================= ANALYSIS ENGINE =================
def scan_logic(df):
    try:
        df = calculate_indicators(df)
        l = df.iloc[-1]
        p, rsi, e9, e21, vwap, st_g = l['Close'], l['RSI'], l['EMA9'], l['EMA21'], l['VWAP'], l['ST_Trend']
        score = 0
        reasons = []
        if e9 > e21: score += 2; reasons.append("Bullish EMA Cross")
        else: score -= 2
        if p > vwap: score += 1; reasons.append("Above VWAP")
        else: score -= 1
        if st_g: score += 1; reasons.append("ST Green")
        else: score -= 1
        
        if score >= 2: sig = "🟢 CALL"
        elif score <= -2: sig = "🔴 PUT"
        else: sig = "⚪ NO TRADE"
        return sig, score, round(p,2), round(rsi,1), reasons
    except: return "⚪ ERROR", 0, 0, 0, []

# ================= APP TABS =================
t1, t2, t3, t4 = st.tabs(["📊 Analysis", "📈 Indices", "🔥 Top 10 Scan", "📰 News"])

with t1:
    sel = st.selectbox("Select Stock:", list(STOCK_MAP.keys()))
    sym = STOCK_MAP[sel]
    
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        # FIX: Try-Except block for NSE verification
        if st.button("🔍 Verify NSE Price"):
            with st.spinner('Fetching NSE Data...'):
                nse_ltp = get_stable_nse_price(sym)
                if isinstance(nse_ltp, (int, float)):
                    st.warning(f"Official NSE LTP: ₹{nse_ltp}")
                else:
                    st.error(f"NSE Error: {nse_ltp}")
            
    df_data = yf.Ticker(sym).history(period="2d", interval="5m")
    if not df_data.empty:
        sig, sc, pr, rs, res = scan_logic(df_data)
        with col_v2:
            st.info(f"App Price (Yahoo): ₹{pr}")
            
        st.subheader(f"Signal: {sig}")
        if sig != "⚪ NO TRADE":
            tgt, sl, ex_msg = get_exit_levels(pr, sig)
            c1, c2, c3 = st.columns(3)
            c1.metric("ENTRY", f"₹{pr}")
            c2.metric("TARGET", f"₹{tgt}")
            c3.metric("SL", f"₹{sl}")
            st.info(f"**💡 Exit:** {ex_msg}")
        
        st.write("---")
        fig = go.Figure(data=[go.Candlestick(x=df_data.index, open=df_data['Open'], high=df_data['High'], low=df_data['Low'], close=df_data['Close'])])
        st.plotly_chart(fig, use_container_width=True)

with t3:
    if st.button("Start Full Scan"):
        res_list = []
        pb = st.progress(0)
        for i, (n, s) in enumerate(STOCK_MAP.items()):
            pb.progress((i+1)/len(STOCK_MAP))
            d = yf.Ticker(s).history(period="2d", interval="5m")
            if not d.empty:
                si, sc, p, r, _ = scan_logic(d)
                if si != "⚪ NO TRADE":
                    t, s_l, _ = get_exit_levels(p, si)
                    res_list.append({"Stock": n, "Signal": si, "Price": p, "Target": t, "SL": s_l})
        if res_list: st.table(pd.DataFrame(res_list))

with t4:
    st.header("📰 News Sentiment & Trade Levels")
    if st.button("Fetch News"):
        news_rows = []
        for n in ["RELIANCE", "HDFC BANK", "SBI", "ONGC"]:
            items = get_indian_news(n)
            d = yf.Ticker(STOCK_MAP[n]).history(period="2d", interval="5m")
            if not d.empty:
                si, sc, p, r, _ = scan_logic(d)
                t, s_l, _ = get_exit_levels(p, si)
                for it in items:
                    news_rows.append({"Stock": n, "Sent.": analyze_sentiment(it['title']), "LTP": p, "TGT": t, "SL": s_l, "Headline": it['title']})
        if news_rows: st.table(pd.DataFrame(news_rows))
