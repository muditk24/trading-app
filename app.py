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
        data = yf.download(stock, period="5d", interval="5m")
        data.dropna(inplace=True)

        if not data.empty:

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

            # Values
            rsi = latest['rsi']
            price = latest['Close']
            ema = latest['ema50']

            if pd.notna(rsi):
                st.write(f"RSI: {float(rsi):.2f}")
            else:
                st.write("RSI: Not available")

            st.write(f"Price: {float(price):.2f}")

            # Trend
            if price > ema:
                trend = "UPTREND"
            else:
                trend = "DOWNTREND"

            st.subheader(f"Trend: {trend}")

            # Signal
            if pd.notna(rsi):
                if rsi < 35 and trend == "UPTREND":
                    st.success("✅ CALL (Buy) Signal")
                elif rsi > 65 and trend == "DOWNTREND":
                    st.error("❌ PUT (Sell) Signal")
                else:
                    st.warning("⚠️ No Strong Signal")

    except:
        st.error("Error loading stock data")

# ================= SMART SCANNER =================

st.header("🔥 Smart Market Scanner (Top 5 Opportunities)")

stocks = [
    "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
    "SBIN.NS","LT.NS","ITC.NS","AXISBANK.NS","KOTAKBANK.NS",
    "HINDUNILVR.NS","BAJFINANCE.NS","ASIANPAINT.NS","MARUTI.NS",
    "TITAN.NS","SUNPHARMA.NS","ULTRACEMCO.NS","WIPRO.NS"
]

results = []

for s in stocks:
    try:
        data = yf.download(s, period="5d", interval="15m")
        data.dropna(inplace=True)

        if data.empty:
            continue

        close_series = data['Close'].squeeze()

        data['rsi'] = ta.momentum.RSIIndicator(close_series).rsi()
        data['ema50'] = ta.trend.EMAIndicator(close_series, window=50).ema_indicator()

        latest = data.iloc[-1]

        rsi = latest['rsi']
        price = latest['Close']
        ema = latest['ema50']

        if pd.isna(rsi):
            continue

        if price > ema:
            trend = "UP"
        else:
            trend = "DOWN"

        signal = "NO TRADE"
        score = 0

        if rsi < 35 and trend == "UP":
            signal = "CALL"
            score = 100 - rsi
        elif rsi > 65 and trend == "DOWN":
            signal = "PUT"
            score = rsi

        if signal != "NO TRADE":
            results.append({
                "Stock": s,
                "RSI": round(float(rsi), 2),
                "Trend": trend,
                "Signal": signal,
                "Score": round(score, 2)
            })

    except:
        continue

# Sort & show top 5
if results:
    df = pd.DataFrame(results)
    df = df.sort_values(by="Score", ascending=False).head(5)

    st.subheader("🔥 Top 5 Best Trades Right Now")
    st.dataframe(df)
else:
    st.write("No strong signals found ❌")

st.write("---")
st.write("⚠️ For learning purpose only")
