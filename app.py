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

            # RSI
            data['rsi'] = ta.momentum.RSIIndicator(close_series).rsi()

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
            price = float(latest['Close'])

            # RSI safe
            try:
                rsi = float(latest['rsi'])
            except:
                rsi = 50

            st.write(f"Price: {round(price,2)}")
            st.write(f"RSI: {round(rsi,2)}")

            # Signal
            if rsi < 40:
                st.success("✅ CALL (Buy Zone)")
            elif rsi > 60:
                st.error("❌ PUT (Sell Zone)")
            else:
                st.warning("⚠️ Sideways")

        else:
            st.error("Stock data not found")

    except:
        st.error("Error loading stock data")

# ================= LIVE SCANNER =================

st.header("🔥 Live Market Scanner")

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

        try:
            rsi = float(latest['rsi'])
        except:
            continue

        if rsi < 45:
            results.append({"Stock": s, "Signal": "CALL", "RSI": round(rsi,2)})
        elif rsi > 55:
            results.append({"Stock": s, "Signal": "PUT", "RSI": round(rsi,2)})

    except:
        continue

if results:
    df = pd.DataFrame(results)
    st.dataframe(df.head(5))
else:
    st.write("No strong live signals")

# ================= LAST DAY BEST =================

st.header("🔥 Last Day Best Trades (Guaranteed)")

last_day_results = []

for s in stocks:
    try:
        data = yf.download(s, period="5d", interval="1d")

        if len(data) < 2:
            continue

        data.dropna(inplace=True)

        prev = data.iloc[-2]
        curr = data.iloc[-1]

        change = ((curr['Close'] - prev['Close']) / prev['Close']) * 100

        signal = "CALL" if change > 0 else "PUT"

        last_day_results.append({
            "Stock": s,
            "Change %": round(change,2),
            "Signal": signal
        })

    except:
        continue

if last_day_results:
    df2 = pd.DataFrame(last_day_results)
    df2 = df2.sort_values(by="Change %", ascending=False)

    st.subheader("📈 Top Gainers (CALL)")
    st.dataframe(df2.head(3))

    st.subheader("📉 Top Losers (PUT)")
    st.dataframe(df2.tail(3))

st.write("⚠️ For learning purpose only")
