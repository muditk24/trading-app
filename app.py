# app.py
import streamlit as st
import pandas as pd
import ta
from upstox_api.api import Upstox
from datetime import datetime, timedelta

st.set_page_config(page_title="Upstox Option Trading Assistant", layout="wide")
st.title("📊 Upstox Option Trading Assistant")

# ----- Upstox API Setup -----
API_KEY = "YOUR_API_KEY"
ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"
u = Upstox(API_KEY, ACCESS_TOKEN)

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
    df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
    
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
    
    # Simple rules (same as your 15+ simplified)
    signal = "NO TRADE"
    if price > ema9 > ema21 and rsi < 65:
        signal = "CALL"
    elif price < ema9 < ema21 and rsi > 35:
        signal = "PUT"
    
    return signal, price, rsi, ema9, ema21, ema50

# ----- UI -----
stock_input = st.text_input("Enter NSE Stock Symbol (e.g. RELIANCE)","RELIANCE")

if stock_input:
    try:
        # Fetch last 5 days, 5-min candles
        end = datetime.now()
        start = end - timedelta(days=5)
        candles = u.get_candle_data(f"NSE_EQ:{stock_input}", "5minute", start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        df = pd.DataFrame(candles)
        if df.empty:
            st.error("No data returned from Upstox API")
        else:
            df['Close'] = pd.to_numeric(df['close'])
            df['Open'] = pd.to_numeric(df['open'])
            df['High'] = pd.to_numeric(df['high'])
            df['Low'] = pd.to_numeric(df['low'])
            
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
            
            st.subheader("💡 Last 5-min Candles")
            st.dataframe(df.tail(10))
            
            st.warning("⚠️ For learning purposes only. Do NOT trade real money blindly.")
    except Exception as e:
        st.error(f"Failed to fetch or analyze data: {e}")
