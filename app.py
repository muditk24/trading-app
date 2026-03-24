import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

# ================= UI SETUP =================
st.set_page_config(page_title="Alpha 9-Candle Scanner", layout="wide", page_icon="🎯")
st.title("🎯 Pro Trader Dashboard (9-Candle Logic)")

# ================= MASTER LIST =================
STOCK_MAP = {
    "RELIANCE": "RELIANCE.NS", "HDFC BANK": "HDFCBANK.NS", "ICICI BANK": "ICICIBANK.NS",
    "SBI": "SBIN.NS", "TCS": "TCS.NS", "INFOSYS": "INFY.NS", "ONGC": "ONGC.NS",
    "PFC": "PFC.NS", "COAL INDIA": "COALINDIA.NS", "TATA MOTORS": "TATAMOTORS.NS",
    "AXIS BANK": "AXISBANK.NS", "BHARTI AIRTEL": "BHARTIARTL.NS", "L&T": "LT.NS",
    "BAJAJ FINANCE": "BAJFINANCE.NS", "ITC": "ITC.NS"
}
INDICES = {"NIFTY 50": "^NSEI", "BANK NIFTY": "^NSEBANK"}

# ================= HELPER FUNCTIONS =================
def get_indian_news(company_name):
    query = urllib.parse.quote(f'"{company_name}" share market news india when:1d')
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        return [{'title': i.find('title').text, 'link': i.find('link').text} for i in root.findall('.//item')[:3]]
    except: return []

def get_atm_strike(price, symbol_name):
    if "NIFTY 50" in symbol_name:
        return round(price / 50) * 50
    elif "BANK NIFTY" in symbol_name:
        return round(price / 100) * 100
    else:
        return round(price)

# ================= CORE LOGIC: 9-CANDLE SCANNER =================
def analyze_9_candles(df, symbol_name="Stock"):
    try:
        if len(df) < 15: return None
        
        df = df.copy()
        df['EMA9'] = ta.trend.EMAIndicator(df['Close'], window=9).ema_indicator()
        df['EMA21'] = ta.trend.EMAIndicator(df['Close'], window=21).ema_indicator()
        df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
        
        # VWAP Logic
        df['Date'] = pd.to_datetime(df.index).date
        df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
        df['VP'] = df['TP'] * df['Volume']
        df['VWAP'] = df.groupby('Date')['VP'].transform('cumsum') / df.groupby('Date')['Volume'].transform('cumsum')

        last_9 = df.tail(9)
        curr = df.iloc[-1]
        price = round(curr['Close'], 2)
        rsi = round(curr['RSI'], 1)
        
        score = 0
        reasons = []
        
        # 1. EMA Check (9 candles)
        if (last_9['EMA9'] > last_9['EMA21']).all(): 
            score += 2; reasons.append("🟢 Strong Bullish Trend (EMA9 > EMA21)")
        elif (last_9['EMA9'] < last_9['EMA21']).all(): 
            score -= 2; reasons.append("🔴 Strong Bearish Trend (EMA9 < EMA21)")
        elif curr['EMA9'] > curr['EMA21']:
            score += 1; reasons.append("🟢 Fresh Bullish EMA Crossover")
        else:
            score -= 1; reasons.append("🔴 Fresh Bearish EMA Crossover")
            
        # 2. VWAP Check
        if price > curr['VWAP']: 
            score += 1; reasons.append("🟢 Price is sustaining Above VWAP")
        else: 
            score -= 1; reasons.append("🔴 Price is Below VWAP")
            
        # 3. RSI Momentum Check
        if 55 < rsi < 75: 
            score += 1; reasons.append(f"🟢 Good Bullish Momentum (RSI: {rsi})")
        elif 25 < rsi < 45: 
            score -= 1; reasons.append(f"🔴 Good Bearish Momentum (RSI: {rsi})")
        else:
            reasons.append(f"⚪ RSI is Sideways/Overbought/Oversold (RSI: {rsi})")

        # Signal Generation
        signal = "⚪ NO TRADE / SIDEWAYS"
        if score >= 3: signal = "🟢 STRONG CALL"
        elif score == 2: signal = "🟢 WEAK CALL (Wait for Setup)"
        elif score <= -3: signal = "🔴 STRONG PUT"
        elif score == -2: signal = "🔴 WEAK PUT (Wait for Setup)"
        
        # Exit & Strike Calculations
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
            "signal": signal, "score": score, "price": price, 
            "rsi": rsi, "target": tgt, "sl": sl, "reasons": reasons,
            "strike": strike_str
        }
    except Exception as e: return None

# ================= TABS =================
t1, t2, t3, t4, t5 = st.tabs(["📊 Stock Analysis", "📈 Indices", "🎯 Recommended Calls/Puts", "🔥 Scanner", "📰 Live News"])

# --- TAB 1: STOCK ---
with t1:
    sel = st.selectbox("🔍 Analyze Specific Stock:", list(STOCK_MAP.keys()))
    df = yf.Ticker(STOCK_MAP[sel]).history(period="3d", interval="5m")
    
    if not df.empty:
        res = analyze_9_candles(df, sel)
        if res:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Current Price", f"₹{res['price']}")
            c2.metric("Setup Score", f"{res['score']} / 4")
            if "CALL" in res['signal']: c3.success(res['signal'])
            elif "PUT" in res['signal']: c3.error(res['signal'])
            else: c3.warning(res['signal'])
            c4.metric("RSI", res['rsi'])

            if "TRADE" not in res['signal']:
                st.info(f"**🎯 EXIT STRATEGY:** Target: **₹{res['target']}** | Stop Loss: **₹{res['sl']}**")
            
            st.write("---")
            c_chart, c_reasons = st.columns([2, 1])
            with c_chart:
                fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
                fig.update_layout(height=400, margin=dict(l=0, r=0, t=30, b=0), title="5-Minute Chart")
                st.plotly_chart(fig, use_container_width=True)
            with c_reasons:
                st.subheader("🧠 Setup Reasoning")
                for r in res['reasons']:
                    st.write(r)

# --- TAB 2: INDICES ---
with t2:
    st.header("📈 Nifty & BankNifty Live")
    cols = st.columns(2)
    for i, (name, sym) in enumerate(INDICES.items()):
        idx_df = yf.Ticker(sym).history(period="2d", interval="5m")
        if not idx_df.empty:
            res = analyze_9_candles(idx_df, name)
            if res:
                with cols[i]:
                    st.subheader(name)
                    st.metric("LTP", f"₹{res['price']}", res['signal'].split(' ')[1] if 'CALL' in res['signal'] or 'PUT' in res['signal'] else None)
                    
                    if "CALL" in res['signal'] or "PUT" in res['signal']:
                        st.success(f"**Strike to Buy:** {res['strike']}")
                        c1, c2 = st.columns(2)
                        c1.write(f"**Target:** ₹{res['target']}")
                        c2.write(f"**SL:** ₹{res['sl']}")
                    else:
                        st.warning("**Status:** Market Sideways. No Options Recommended right now.")
                    
                    st.write(f"**Score:** {res['score']} | **RSI:** {res['rsi']}")
                    for r in res['reasons']: st.caption(r)

# --- TAB 3: RECOMMENDED CALLS & PUTS (NEW TAB) ---
with t3:
    st.header("🎯 Active Buy Recommendations")
    st.write("Showing only 'Strong' Call and Put signals from the entire market...")
    if st.button("🔍 Find Setup"):
        recom_list = []
        with st.spinner("Checking setups..."):
            all_assets = {**INDICES, **STOCK_MAP}
            for name, sym in all_assets.items():
                temp_df = yf.Ticker(sym).history(period="2d", interval="5m")
                if not temp_df.empty:
                    res = analyze_9_candles(temp_df, name)
                    if res and ("STRONG" in res['signal'] or "WEAK" in res['signal']):
                        recom_list.append({
                            "Asset": name,
                            "Signal": res['signal'],
                            "Strike/Action": res['strike'],
                            "Entry (Spot)": res['price'],
                            "Target": res['target'],
                            "Stop Loss": res['sl'],
                            "Score": res['score']
                        })
        if recom_list:
            st.dataframe(pd.DataFrame(recom_list).style.map(lambda x: 'background-color: #d4edda' if 'CALL' in str(x) else ('background-color: #f8d7da' if 'PUT' in str(x) else ''), subset=['Signal']), use_container_width=True)
        else:
            st.info("No active Calls/Puts recommended right now based on 9-candle logic.")

# --- TAB 4: DYNAMIC SCANNER ---
with t4:
    st.header("🔥 Top Momentum Scanner")
    st.write("Sorting by Signal Strength and RSI Momentum...")
    if st.button("🚀 Start Market Scan"):
        results = []
        pb = st.progress(0)
        for i, (n, s) in enumerate(STOCK_MAP.items()):
            pb.progress((i+1)/len(STOCK_MAP))
            scan_df = yf.Ticker(s).history(period="3d", interval="5m")
            if not scan_df.empty:
                r = analyze_9_candles(scan_df, n)
                if r:
                    results.append({
                        "Stock": n, "Signal": r['signal'], "Score": r['score'], 
                        "RSI": r['rsi'], "LTP": r['price'], "Target": r['target'], "SL": r['sl']
                    })
        
        if results:
            res_df = pd.DataFrame(results)
            res_df['AbsScore'] = res_df['Score'].abs() 
            res_df = res_df.sort_values(by=['AbsScore', 'RSI'], ascending=[False, False]).drop(columns=['AbsScore'])
            st.dataframe(res_df.style.map(lambda x: 'color: green' if 'CALL' in str(x) else ('color: red' if 'PUT' in str(x) else ''), subset=['Signal']), use_container_width=True)

# --- TAB 5: DYNAMIC NEWS ---
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
                st.warning(f"No fresh news found for {news_sel} in the last 24 hours.")
