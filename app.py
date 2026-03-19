import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("📊 Simple Option Trading Assistant")

# ================= SAFE =================
def safe(v, d=0):
    try:
        return float(v)
    except:
        return d

# ================= OPTION =================
def option_trade(price, signal):
    strike = round(price / 50) * 50

    if signal == "CALL":
        return f"{strike} CE", price, round(price*1.03,2), round(price*0.98,2)

    if signal == "PUT":
        return f"{strike} PE", price, round(price*0.97,2), round(price*1.02,2)

    return None

# ================= ANALYSIS =================
def analyze(data):
    data = data.copy().dropna()

    close = data['Close']

    # Indicators
    data['ema20'] = ta.trend.EMAIndicator(close, 20).ema_indicator()
    data['ema50'] = ta.trend.EMAIndicator(close, 50).ema_indicator()
    data['rsi'] = ta.momentum.RSIIndicator(close).rsi()

    latest = data.iloc[-1]

    price = safe(latest['Close'])
    ema20 = safe(latest['ema20'])
    ema50 = safe(latest['ema50'])
    rsi = safe(latest['rsi'],50)

    # ===== LOGIC (CLEAN) =====
    if price > ema20 and ema20 > ema50 and rsi < 60:
        signal = "CALL"
    elif price < ema20 and ema20 < ema50 and rsi > 40:
        signal = "PUT"
    else:
        signal = "NO TRADE"

    return signal, price, rsi, ema20, ema50

# ================= UI =================
stock = st.text_input("Enter Stock", "RELIANCE.NS")

if stock:
    data = yf.download(stock, period="3mo", interval="1d")

    if data.empty:
        st.error("Data nahi aa raha")
    else:
        signal, price, rsi, ema20, ema50 = analyze(data)

        # Chart
        fig = go.Figure(data=[go.Candlestick(
            x=data.index,
            open=data['Open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close']
        )])
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("## 📊 TRADE OUTPUT")

        st.write(f"💰 Price: {price}")
        st.write(f"📉 RSI: {round(rsi,2)}")
        st.write(f"📊 EMA20: {round(ema20,2)}")
        st.write(f"📊 EMA50: {round(ema50,2)}")

        st.write(f"## 🚀 Signal: {signal}")

        # Trade setup
        trade = option_trade(price, signal)

        if trade:
            option, entry, target, sl = trade

            st.markdown("### 🎯 Trade Setup")
            st.write(f"Option: {option}")
            st.write(f"Entry: {entry}")
            st.write(f"Target: {target}")
            st.write(f"Stop Loss: {sl}")

st.write("⚠️ For learning purpose only")
