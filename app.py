import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go

st.title("📊 AI Option Trading Assistant")

stock = st.text_input("Enter Stock (e.g. RELIANCE.NS)", "RELIANCE.NS")

if stock:
    data = yf.download(stock, period="5d", interval="5m")
    data.dropna(inplace=True)

    close_series = data['Close'].squeeze()

    data['rsi'] = ta.momentum.RSIIndicator(close_series).rsi()
    data['ema50'] = ta.trend.EMAIndicator(close_series, window=50).ema_indicator()

    latest = data.iloc[-1]

    fig = go.Figure(data=[go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close']
    )])

    st.plotly_chart(fig)

    st.write(f"RSI: {latest['rsi']:.2f}")
    st.write(f"Price: {latest['Close']:.2f}")

    if latest['Close'] > latest['ema50']:
        trend = "UPTREND"
    else:
        trend = "DOWNTREND"

    st.subheader(f"Trend: {trend}")

    if latest['rsi'] < 35 and trend == "UPTREND":
        st.success("✅ CALL (Buy) Signal")
    elif latest['rsi'] > 65 and trend == "DOWNTREND":
        st.error("❌ PUT (Sell) Signal")
    else:
        st.warning("⚠️ No Strong Signal")
