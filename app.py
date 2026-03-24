import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
from datetime import datetime

# ================= UI SETUP =================
st.set_page_config(page_title="Alpha 9-Candle Pro", layout="wide", page_icon="🚀")
st.title("🚀 Alpha Pro: 9-Candle Execution Engine")

# ================= CONFIG & CONSTANTS =================
STOCK_MAP = {
    "NIFTY 50": "^NSEI", "BANK NIFTY": "^NSEBANK",
    "RELIANCE": "RELIANCE.NS", "HDFC BANK": "HDFCBANK.NS", "ICICI BANK": "ICICIBANK.NS",
    "SBI": "SBIN.NS", "TCS": "TCS.NS"
}

# ================= CORE LOGIC =================
def get_strike_price(price, step=50):
    """Calculates the At-The-Money (ATM) Strike Price"""
    return round(price / step) * step

def analyze_pro_logic(df, symbol):
    if len(df) < 30: return None
    
    # Technical Indicators
    df['EMA9'] = ta.trend.EMAIndicator(df['Close'], window=9).ema_indicator()
    df['EMA21'] = ta.trend.EMAIndicator(df['Close'], window=21).ema_indicator()
    df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
    
    # VWAP Calculation
    df['Date'] = pd.to_datetime(df.index).date
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (df['TP'] * df['Volume']).groupby(df['Date']).cumsum() / df['Volume'].groupby(df['Date']).cumsum()

    curr = df.iloc[-1]
    prev = df.iloc[-2]
    price = round(curr['Close'], 2)
    
    # Signal Logic
    signal = "WAITING"
    strike = get_strike_price(price, 50 if "NIFTY" in symbol else 100)
    
    # BULLISH CONDITION
    # 1. Price > EMA9 > EMA21
    # 2. Price > VWAP
    # 3. RSI crossing 55 upwards
    is_bullish = curr['EMA9'] > curr['EMA21'] and price > curr['VWAP'] and curr['RSI'] > 55
    is_bearish = curr['EMA9'] < curr['EMA21'] and price < curr['VWAP'] and curr['RSI'] < 45

    if is_bullish:
        signal = "ENTRY: BUY CALL"
        sl = round(min(curr['EMA21'], price * 0.995), 2) # SL at EMA21 or 0.5%
        target = round(price + (price - sl) * 2, 2)    # 1:2 Risk-Reward
        opt_type = "CE"
    elif is_bearish:
        signal = "ENTRY: BUY PUT"
        sl = round(max(curr['EMA21'], price * 1.005), 2)
        target = round(price - (sl - price) * 2, 2)
        opt_type = "PE"
    else:
        signal = "NO TRADE (Wait for Trend)"
        sl = target = opt_type = 0

    return {
        "price": price, "signal": signal, "strike": f"{strike} {opt_type}",
        "target": target, "sl": sl, "rsi": round(curr['RSI'], 1),
        "ema9": curr['EMA9'], "ema21": curr['EMA21'], "vwap": curr['VWAP']
    }

# ================= MAIN UI =================
sel_name = st.sidebar.selectbox("Select Asset", list(STOCK_MAP.keys()))
symbol = STOCK_MAP[sel_name]

# Fetch Data
data = yf.Ticker(symbol).history(period="2d", interval="5m")

if not data.empty:
    analysis = analyze_pro_logic(data, sel_name)
    
    # Header Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("LTP", f"₹{analysis['price']}")
    m2.metric("RSI (5m)", analysis['rsi'])
    
    if "BUY" in analysis['signal']:
        m3.success(analysis['signal'])
        st.balloons()
    else:
        m3.warning(analysis['signal'])
    
    # Trading Card
    if "ENTRY" in analysis['signal']:
        st.markdown(f"""
        ### ⚡ Trade Execution Details
        | Recommended Strike | Entry Price | Stop Loss (SL) | Target (T1) | Risk:Reward |
        | :--- | :--- | :--- | :--- | :--- |
        | **{analysis['strike']}** | Above ₹{analysis['price']} | ₹{analysis['sl']} | ₹{analysis['target']} | 1:2 |
        """)
        st.info(f"💡 **Exit Logic:** Exit immediately if candle closes below EMA21 (for Calls) or above EMA21 (for Puts).")

    # --- TradingView-Style Chart ---
    fig = go.Figure()

    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="Price"
    ))

    # Indicators
    fig.add_trace(go.Scatter(x=data.index, y=data['EMA9'], line=dict(color='blue', width=1), name="EMA 9"))
    fig.add_trace(go.Scatter(x=data.index, y=data['EMA21'], line=dict(color='orange', width=1), name="EMA 21"))
    fig.add_trace(go.Scatter(x=data.index, y=data['VWAP'], line=dict(color='purple', width=1, dash='dash'), name="VWAP"))

    fig.update_layout(
        height=600, 
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        title=f"{sel_name} Real-time Technical Setup"
    )
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("Market Data Unavailable. Please check symbol or internet connection.")

# ================= FOOTER SCANNER =================
with st.expander("🔍 Multi-Symbol Quick Scan"):
    scan_results = []
    for name, sym in STOCK_MAP.items():
        s_df = yf.Ticker(sym).history(period="2d", interval="5m")
        res = analyze_pro_logic(s_df, name)
        if res:
            scan_results.append({"Stock": name, "Signal": res['signal'], "Price": res['price'], "RSI": res['rsi']})
    
    st.table(pd.DataFrame(scan_results))
