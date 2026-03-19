import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("📊 AI Option Trading Assistant (Fixed Version)")

# ================= SAFE =================
def safe(v, d=0):
    try:
        return float(v)
    except:
        return d

# ================= OPTION =================
def option_trade(price, signal):
    strike = round(price / 50) * 50

    if "CALL" in signal:
        return f"{strike} CE", price, round(price*1.02,2), round(price*0.99,2)

    if "PUT" in signal:
        return f"{strike} PE", price, round(price*0.98,2), round(price*1.01,2)

    return None

# ================= ANALYSIS =================
def analyze(data):
    try:
        data = data.copy().dropna()

        if len(data) < 30:
            return "NO DATA", 0, 0, 0, []

        close = data['Close']

        # Indicators
        data['ema9'] = ta.trend.EMAIndicator(close, 9).ema_indicator()
        data['ema21'] = ta.trend.EMAIndicator(close, 21).ema_indicator()
        data['rsi'] = ta.momentum.RSIIndicator(close).rsi()

        latest = data.iloc[-1]
        prev = data.iloc[-2]

        price = safe(latest['Close'])
        ema9 = safe(latest['ema9'])
        ema21 = safe(latest['ema21'])
        rsi = safe(latest['rsi'],50)

        score = 0
        checks = []

        # SIMPLE RULES (loosened)
        if ema9 > ema21:
            score += 1
            checks.append("EMA Bullish")

        if price > prev['Close']:
            score += 1
            checks.append("Price Up")

        if rsi < 60:
            score += 1
            checks.append("RSI Safe")

        if rsi > 40:
            score += 1
            checks.append("Momentum OK")

        # SIGNAL (loose threshold)
        if score >= 3:
            signal = "CALL"
        elif score <= 1:
            signal = "PUT"
        else:
            signal = "SIDEWAYS"

        return signal, score, price, rsi, checks

    except:
        return "ERROR", 0, 0, 0, []

# ================= UI =================
stock = st.text_input("Enter Stock", "RELIANCE.NS")

if stock:
    try:
        data = yf.download(stock, period="1mo", interval="1d")

        if data.empty:
            st.error("❌ Data not coming (check stock name)")
        else:
            result = analyze(data)
            signal, score, price, rsi, checks = result

            # Chart
            fig = go.Figure(data=[go.Candlestick(
                x=data.index,
                open=data['Open'],
                high=data['High'],
                low=data['Low'],
                close=data['Close']
            )])
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("## 🚀 TRADE OUTPUT")

            st.write(f"Signal: {signal}")
            st.write(f"Score: {score}")
            st.write(f"Price: {price}")
            st.write(f"RSI: {rsi}")

            # OPTION
            trade = option_trade(price, signal)

            if trade:
                option, entry, target, sl = trade
                st.markdown("### 🎯 Trade Setup")
                st.write(f"Option: {option}")
                st.write(f"Entry: {entry}")
                st.write(f"Target: {target}")
                st.write(f"SL: {sl}")

            st.markdown("### 🧠 Checks")
            for c in checks:
                st.write(f"✔️ {c}")

    except Exception as e:
        st.error(f"Error: {e}")

# ================= SCANNER =================
st.header("🔥 Scanner")

stocks = ["RELIANCE.NS","TCS.NS","INFY.NS","SBIN.NS"]

rows = []

for s in stocks:
    try:
        data = yf.download(s, period="1mo", interval="1d")

        if data.empty:
            continue

        signal, score, price, rsi, _ = analyze(data)

        rows.append({
            "Stock": s,
            "Signal": signal,
            "Price": price
        })

    except:
        continue

if rows:
    df = pd.DataFrame(rows)
    st.dataframe(df)
else:
    st.write("No data")

st.write("⚠️ For learning purpose only")
