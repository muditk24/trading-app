import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
import datetime as dt
from zoneinfo import ZoneInfo

st.set_page_config(layout="wide")
st.title("📊 AI Option Trading Assistant (Live + Stable)")

# ================= SAFE =================
def safe(v, d=0):
    try:
        return float(v)
    except:
        return d

# ================= MARKET MODE =================
def fetch_data(symbol):
    ist = ZoneInfo("Asia/Kolkata")
    now = dt.datetime.now(ist).time()

    market_open = dt.time(9, 15)
    market_close = dt.time(15, 30)

    if market_open <= now <= market_close:
        period = "5d"
        interval = "5m"
        mode = "LIVE (Intraday)"
    else:
        period = "3mo"
        interval = "1d"
        mode = "CLOSED (EOD Data)"

    data = yf.download(symbol, period=period, interval=interval, progress=False)

    return data, mode

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

        if len(data) < 20:
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

        # RULES (balanced)
        if ema9 > ema21:
            score += 1
            checks.append("EMA Bullish")

        if price > prev['Close']:
            score += 1
            checks.append("Price Up")

        if 40 < rsi < 65:
            score += 1
            checks.append("RSI Healthy")

        if rsi < 70:
            score += 1

        # SIGNAL
        if score >= 3:
            signal = "🔥 CALL"
        elif score <= 1:
            signal = "🔥 PUT"
        else:
            signal = "SIDEWAYS"

        return signal, score, price, rsi, checks

    except:
        return "ERROR", 0, 0, 0, []

# ================= UI =================
stock = st.text_input("Enter Stock (e.g. RELIANCE.NS)", "RELIANCE.NS")

if stock:
    data, mode = fetch_data(stock)

    if data.empty:
        st.error("❌ Data nahi aa raha (symbol check kar)")
    else:
        signal, score, price, rsi, checks = analyze(data)

        # Chart
        fig = go.Figure(data=[go.Candlestick(
            x=data.index,
            open=data['Open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close']
        )])
        st.plotly_chart(fig, use_container_width=True)

        # Mode show
        st.info(f"📡 Mode: {mode}")

        # Confidence
        confidence = min(90, max(50, abs(score)*15))

        if score >= 3:
            risk = "LOW"
        elif score == 2:
            risk = "MEDIUM"
        else:
            risk = "HIGH"

        st.markdown("## 🚀 TRADE DECISION")
        st.write(f"### {signal}")
        st.write(f"📈 Confidence: {confidence}%")
        st.write(f"💰 Price: {price}")

        # Trade
        trade = option_trade(price, signal)

        if trade:
            option, entry, target, sl = trade

            st.markdown("### 🎯 Trade Setup")
            st.write(f"Option: {option}")
            st.write(f"Entry: {entry}")
            st.write(f"Target: {target}")
            st.write(f"Stop Loss: {sl}")

        st.markdown("### 🧠 Why this trade?")
        for c in checks:
            st.write(f"✔️ {c}")

        st.write(f"⚠️ Risk Level: {risk}")

# ================= SCANNER =================
st.header("🔥 Smart Scanner")

stocks = ["RELIANCE.NS","TCS.NS","INFY.NS","SBIN.NS","ICICIBANK.NS"]

rows = []

for s in stocks:
    try:
        data, _ = fetch_data(s)

        if data.empty:
            continue

        signal, score, price, rsi, _ = analyze(data)

        confidence = min(90, max(50, abs(score)*15))

        rows.append({
            "Stock": s,
            "Signal": signal,
            "Confidence": confidence,
            "Price": price
        })

    except:
        continue

if rows:
    df = pd.DataFrame(rows)
    df = df.sort_values(by="Confidence", ascending=False)
    st.dataframe(df, use_container_width=True)
else:
    st.write("No data")

st.write("⚠️ For learning purpose only")
