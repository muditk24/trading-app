import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go

st.title("📊 AI Option Trading Assistant")

# ================= SINGLE STOCK =================
stock = st.text_input("Enter Stock (e.g. RELIANCE.NS)", "RELIANCE.NS")

if stock:
    data = yf.download(stock, period="3mo", interval="1d")

    if not data.empty:
        data.dropna(inplace=True)

        close_series = data['Close'].squeeze()

        data['rsi'] = ta.momentum.RSIIndicator(close_series).rsi()
        data['ema50'] = ta.trend.EMAIndicator(close_series, window=50).ema_indicator()

        latest = data.iloc[-1]

        # Chart
        fig = go.Figure(data=[go.Candlestick(
            x=data.index,
            open=data['Open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close']
        )])
        st.plotly_chart(fig)

        rsi = latest['rsi']
        price = latest['Close']
        ema = latest['ema50']

        st.write(f"Price: {round(float(price),2)}")

        if pd.notna(rsi):
            st.write(f"RSI: {round(float(rsi),2)}")

            if price > ema:
                trend = "UPTREND"
            else:
                trend = "DOWNTREND"

            st.subheader(f"Trend: {trend}")

            if rsi < 40:
                st.success("✅ CALL (Buy Zone)")
            elif rsi > 60:
                st.error("❌ PUT (Sell Zone)")
            else:
                st.warning("⚠️ Sideways / No Trade")

        else:
            st.write("RSI not available")

    else:
        st.error("Stock data not found")

# ================= SMART SCANNER =================

st.header("🔥 Top 5 Opportunities")

stocks = [
    "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
    "SBIN.NS","ITC.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS"
]

results = []

for s in stocks:
    try:
        data = yf.download(s, period="3mo", interval="1d")
        data.dropna(inplace=True)

        if data.empty:
            continue

        close_series = data['Close'].squeeze()

        data['rsi'] = ta.momentum.RSIIndicator(close_series).rsi()
        latest = data.iloc[-1]

        rsi = latest['rsi']

        if pd.isna(rsi):
            continue

        signal = "HOLD"
        score = 0

        if rsi < 40:
            signal = "CALL"
            score = 100 - rsi
        elif rsi > 60:
            signal = "PUT"
            score = rsi

        if signal != "HOLD":
            results.append({
                "Stock": s,
                "RSI": round(float(rsi),2),
                "Signal": signal,
                "Score": round(score,2)
            })

    except:
        continue

if results:
    df = pd.DataFrame(results)
    df = df.sort_values(by="Score", ascending=False).head(5)

    st.dataframe(df)
else:
    st.write("No signals right now")

st.write("⚠️ For learning purpose only")
