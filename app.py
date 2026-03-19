# app.py
import streamlit as st
import yfinance as yf
import pandas as pd
import ta
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(page_title="AI Option Trading Assistant", layout="wide")
st.title("📊 AI Option Trading Assistant (Yahoo Finance)")

# ----- Helper Functions -----
def safe(x, default=50):
    try:
        return float(x)
    except:
        return default

def option_trade(price, signal):
    strike = round(price / 50) * 50
    if signal == "CALL":
        return f"{strike} CE", price, round(price*1.03,2), round(price*0.98,2)
    elif signal == "PUT":
        return f"{strike} PE", price, round(price*0.97,2), round(price*1.02,2)
    return None

def analyze(df):
    df = df.copy().dropna()
    df['Close'] = pd.to_numeric(df['Close'], errors='coerce').dropna()
    
    # Indicators
    df['ema9'] = ta.trend.EMAIndicator(df['Close'], 9).ema_indicator()
    df['ema21'] = ta.trend.EMAIndicator(df['Close'], 21).ema_indicator()
    df['ema50'] = ta.trend.EMAIndicator(df['Close'], 50).ema_indicator()
    df['rsi'] = ta.momentum.RSIIndicator(df['Close']).rsi()
    
    latest = df.iloc[-1]
    price = safe(latest['Close'])
    ema9 = safe(latest['ema9'])
    ema21 = safe(latest['ema21'])
    ema50 = safe(latest['ema50'])
    rsi = safe(latest['rsi'],50)
    
    # Simple Trading Rules
    signal = "NO TRADE"
    if price > ema9 > ema21 and rsi < 65:
        signal = "CALL"
    elif price < ema9 < ema21 and rsi > 35:
        signal = "PUT"
    
    return signal, price, rsi, ema9, ema21, ema50

# ----- UI -----
stock_input = st.text_input("Enter NSE Stock Symbol (e.g. RELIANCE.NS)","RELIANCE.NS")

if stock_input:
    try:
        end = datetime.now()
        start = end - timedelta(days=5)
        df = yf.download(stock_input, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), interval="15m")
        
        if df.empty:
            st.error("No data returned from Yahoo Finance")
        else:
            signal, price, rsi, ema9, ema21, ema50 = analyze(df)
            trade = option_trade(price, signal)
            
            st.subheader(f"Latest Analysis for {stock_input}")
            st.write(f"Price: {price:.2f} | EMA9: {ema9:.2f} | EMA21: {ema21:.2f} | EMA50: {ema50:.2f} | RSI: {rsi:.2f}")
            st.write(f"✅ Suggested Trade: **{signal}**")
            
            if trade:
                option, entry, target, sl = trade
                st.markdown("### 🎯 Trade Setup")
                st.write(f"Option: {option}")
                st.write(f"Entry: {entry}")
                st.write(f"Target: {target}")
                st.write(f"Stop Loss: {sl}")
            
            # Candlestick chart
            fig = go.Figure(data=[go.Candlestick(
                x=df.index,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close']
            )])
            st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("💡 Last 10 Candles")
            st.dataframe(df.tail(10))
            
            st.warning("⚠️ For learning purposes only. Do NOT trade real money blindly.")
    except Exception as e:
        st.error(f"Failed to fetch or analyze data: {e}")
