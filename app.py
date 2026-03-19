import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go

st.title("📊 AI Option Trading Assistant")

# ================= SINGLE STOCK =================
stock = st.text_input("Enter Stock (e.g. RELIANCE.NS)", "RELIANCE.NS")

if stock:
    try:
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

            # SAFE VALUES
            rsi = float(latest['rsi']) if pd.notna(latest['rsi']) else 0
            price = float(latest['Close'])
            ema = float(latest['ema50']) if pd.notna(latest['ema50']) else price

            st.write(f"Price: {round(price,2)}")
            st.write(f"RSI: {round(rsi,2)}")

            # Trend
            if price > ema:
                trend = "UPTREND"
            else:
                trend = "DOWNTREND"

            st.subheader(f"Trend: {trend}")

            # Signal
            if rsi < 40:
                st.success("✅ CALL (Buy Zone)")
            elif rsi > 60:
                st.error("❌ PUT (Sell Zone)")
            else:
                st.warning("⚠️ Sideways / No Trade")

        else:
            st.error("Stock data not found")

    except Exception as e:
        st.error("Error loading stock data")

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

        if data.empty:
            continue

        data.dropna(inplace=True)

        close_series = data['Close'].squeeze()
        data['rsi'] = ta.momentum.RSIIndicator(close_series).rsi()

        latest = data.iloc[-1]

        if pd.isna(latest['rsi']):
            continue

        rsi = float(latest['rsi'])

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
                "RSI": round(rsi,2),
                "Signal": signal,
                "Score": round(score,2)
            })

    except:
        continue

# Show top 5
if results:
    df = pd.DataFrame(results)
    df = df.sort_values(by="Score", ascending=False).head(5)
    st.dataframe(df)
else:
    st.write("No signals right now")

st.write("⚠️ For learning purpose only")
