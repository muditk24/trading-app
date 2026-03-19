import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
import numpy as np
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime

# ================= UI SETUP =================
st.set_page_config(page_title="Pro Options Trader", layout="wide", page_icon="📈")

# ================= MASTER STOCK LIST (NIFTY 100) =================
STOCK_MAP = {
    "RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS", "HDFC BANK": "HDFCBANK.NS", "ICICI BANK": "ICICIBANK.NS",
    "INFOSYS": "INFY.NS", "SBI": "SBIN.NS", "BHARTI AIRTEL": "BHARTIARTL.NS", "ITC": "ITC.NS",
    "L&T": "LT.NS", "BAJAJ FINANCE": "BAJFINANCE.NS", "KOTAK BANK": "KOTAKBANK.NS", "AXIS BANK": "AXISBANK.NS",
    "HCL TECH": "HCLTECH.NS", "ASIAN PAINTS": "ASIANPAINT.NS", "MARUTI": "MARUTI.NS", "SUN PHARMA": "SUNPHARMA.NS",
    "TATA MOTORS": "TATAMOTORS.NS", "ULTRATECH CEMENT": "ULTRACEMCO.NS", "NTPC": "NTPC.NS", "M&M": "M&M.NS",
    "ONGC": "ONGC.NS", "COAL INDIA": "COALINDIA.NS", "PFC": "PFC.NS", "GODREJ PROPERTIES": "GODREJPROP.NS",
    "GODREJ CONSUMER": "GODREJCP.NS", "WIPRO": "WIPRO.NS", "ADANI ENTERPRISES": "ADANIENT.NS",
    "TATA STEEL": "TATASTEEL.NS", "ZOMATO": "ZOMATO.NS", "HAL": "HAL.NS", "BEL": "BEL.NS"
}

# ================= HELPER FUNCTIONS =================
def safe_float(val, default=0):
    try: return float(val)
    except: return default

def analyze_sentiment(headline):
    text = str(headline).lower()
    pos = ['surges', 'jumps', 'gains', 'profit', 'buy', 'wins', 'order', 'up', 'positive', 'high', 'dividend']
    neg = ['falls', 'drops', 'loss', 'sell', 'crash', 'down', 'negative', 'low', 'penalty', 'resigns', 'weak']
    
    pos_count = sum(1 for word in pos if word in text)
    neg_count = sum(1 for word in neg if word in text)
    
    if pos_count > neg_count: return "🟢 Positive"
    elif neg_count > pos_count: return "🔴 Negative"
    else: return "⚪ Neutral"

def get_indian_news(company_name):
    search_term = f'"{company_name}" share market news india'
    query = urllib.parse.quote(search_term)
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        news_items = []
        for item in root.findall('.//item')[:2]: 
            title = item.find('title').text
            link = item.find('link').text
            clean_title = title.rsplit(' - ', 1)[0] if ' - ' in title else title
            news_items.append({'title': clean_title, 'link': link})
        return news_items
    except: return []

# ================= TECHNICAL INDICATORS =================
def calculate_vwap(df):
    df = df.copy()
    df['Date'] = pd.to_datetime(df.index).date
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    if df['Volume'].sum() == 0: return df['TP']
    df['VP'] = df['TP'] * df['Volume']
    df['Cum_Vol'] = df.groupby('Date')['Volume'].cumsum()
    df['Cum_VP'] = df.groupby('Date')['VP'].cumsum()
    return df['Cum_VP'] / df['Cum_Vol']

def calculate_supertrend(df):
    df = df.copy()
    atr = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=10).average_true_range()
    hl2 = (df['High'] + df['Low']) / 2
    ub = hl2 + (3 * atr)
    lb = hl2 - (3 * atr)
    it = [True] * len(df)
    for i in range(1, len(df)):
        if df['Close'].iloc[i] > ub.iloc[i-1]: it[i] = True
        elif df['Close'].iloc[i] < lb.iloc[i-1]: it[i] = False
        else: it[i] = it[i-1]
    return it

# ================= OPTION LOGIC =================
def option_trade(symbol, price, signal):
    step = 100 if "^NSEBANK" in symbol else 50 if "^NSEI" in symbol else 20
    strike = round(price / step) * step
    
    # Force levels calculation even if signal is weak
    if "PUT" in signal or "Negative" in signal:
        return f"{strike} PE", price, round(price*0.96, 2), round(price*1.02, 2)
    else: # Default Call levels
        return f"{strike} CE", price, round(price*1.04, 2), round(price*0.98, 2)

# ================= ANALYSIS ENGINE =================
def analyze_stock(data, is_index=False):
    try:
        data = data.copy()
        data.dropna(inplace=True)
        close = data['Close']
        data['EMA9'] = ta.trend.EMAIndicator(close, window=9).ema_indicator()
        data['EMA21'] = ta.trend.EMAIndicator(close, window=21).ema_indicator()
        data['RSI'] = ta.momentum.RSIIndicator(close).rsi()
        data['VWAP'] = calculate_vwap(data)
        data['ST_Green'] = calculate_supertrend(data)
        
        latest = data.iloc[-1]
        price = safe_float(latest['Close'])
        ema9, ema21, rsi, vwap = safe_float(latest['EMA9']), safe_float(latest['EMA21']), safe_float(latest['RSI']), safe_float(latest['VWAP'])
        st_green = latest['ST_Green']
        
        c_score = 0; p_score = 0; reasons = []
        if ema9 > ema21: c_score += 2; reasons.append("EMA Crossover")
        else: p_score += 2
        if st_green: c_score += 1; reasons.append("Supertrend Bullish")
        else: p_score += 1
        if price > vwap: c_score += 1; reasons.append("Above VWAP")
        else: p_score += 1
        
        sig = "⚪ NO TRADE"
        if c_score >= 3: sig = "🟢 CALL"
        elif p_score >= 3: sig = "🔴 PUT"
        
        return sig, max(c_score, p_score), price, round(rsi, 2), reasons
    except: return None

# ================= APP TABS =================
tab1, tab2, tab3, tab4 = st.tabs(["📊 Single Stock", "📈 Indices", "🔥 Top 10 Scan", "📰 News Analysis"])

with tab1:
    sel = st.selectbox("Select Stock:", list(STOCK_MAP.keys()))
    sym = STOCK_MAP[sel]
    data = yf.Ticker(sym).history(period="5d", interval="15m")
    if not data.empty:
        sig, score, pr, rsi, res = analyze_stock(data)
        st.metric(f"{sel} Price", f"₹{pr}", delta=sig)
        st.subheader("🎯 Setup")
        tr = option_trade(sym, pr, sig)
        st.write(f"**Strike:** {tr[0]} | **TGT:** {tr[2]} | **SL:** {tr[3]}")
        fig = go.Figure(data=[go.Candlestick(x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'])])
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    idx = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK"}
    for k, v in idx.items():
        d = yf.Ticker(v).history(period="5d", interval="15m")
        if not d.empty:
            s, sc, p, r, rs = analyze_stock(d, True)
            st.write(f"### {k}: {s} (₹{p})")

with tab3:
    if st.button("Run Top 10 Scan"):
        results = []
        p_bar = st.progress(0)
        for i, (n, s) in enumerate(STOCK_MAP.items()):
            p_bar.progress((i+1)/len(STOCK_MAP))
            d = yf.Ticker(s).history(period="5d", interval="15m")
            if not d.empty:
                res = analyze_stock(d)
                if res and res[0] != "⚪ NO TRADE":
                    results.append({"Stock": n, "Signal": res[0], "Price": res[2], "Score": res[1]})
        if results: st.table(pd.DataFrame(results).sort_values(by="Score", ascending=False).head(10))

with tab4:
    st.header("📰 News + Levels Recommendation")
    leaders = ["RELIANCE", "HDFC BANK", "ICICI BANK", "SBI", "TCS", "INFOSYS", "ONGC"]
    if st.button("Fetch News & Recommendations 🚀"):
        rows = []
        for n in leaders:
            news = get_indian_news(n)
            d = yf.Ticker(STOCK_MAP[n]).history(period="5d", interval="15m")
            if not d.empty:
                sig, sc, pr, rsi, res = analyze_stock(d)
                for item in news:
                    sent = analyze_sentiment(item['title'])
                    # Recommendation Logic: Use Tech if available, else Fallback to Sentiment
                    final_sig = sig if sig != "⚪ NO TRADE" else ("🔴 PUT" if sent == "🔴 Negative" else "🟢 CALL")
                    rec = option_trade(STOCK_MAP[n], pr, final_sig)
                    rows.append({
                        "Stock": n,
                        "News Sentiment": sent,
                        "Tech Signal": sig,
                        "RECOMMENDED TRADE": f"{rec[0]} @ {pr}",
                        "TARGET": rec[2],
                        "STOPLOSS": rec[3],
                        "Headline": item['title']
                    })
        if rows: st.dataframe(pd.DataFrame(rows), use_container_width=True)

