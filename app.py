import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("📊 AI Option Trading Assistant (Rulebook Pro)")

# ================= SAFE FLOAT =================
def safe(v, d=0):
    try:
        return float(v)
    except:
        return d

# ================= OPTION LOGIC =================
def option_trade(price, signal):
    strike = round(price / 50) * 50

    if signal == "CALL":
        return f"{strike} CE", price, round(price*1.02,2), round(price*0.99,2)

    if signal == "PUT":
        return f"{strike} PE", price, round(price*0.98,2), round(price*1.01,2)

    return None

# ================= CORE RULE ENGINE =================
def analyze(data):
    try:
        data = data.copy()
        data.dropna(inplace=True)

        if len(data) < 50:
            return None

        close = data['Close']

        # Indicators
        data['ema9'] = ta.trend.EMAIndicator(close, 9).ema_indicator()
        data['ema21'] = ta.trend.EMAIndicator(close, 21).ema_indicator()
        data['rsi'] = ta.momentum.RSIIndicator(close).rsi()

        data['vwap'] = (data['Volume'] * (data['High'] + data['Low'] + data['Close'])/3).cumsum() / data['Volume'].cumsum()

        latest = data.iloc[-1]
        prev = data.iloc[-2]

        price = safe(latest['Close'])
        ema9 = safe(latest['ema9'])
        ema21 = safe(latest['ema21'])
        rsi = safe(latest['rsi'],50)
        vwap = safe(latest['vwap'])

        volume = safe(latest['Volume'])
        avg_vol = safe(data['Volume'].mean())

        score = 0
        checks = []

        # ===== CHECKS =====

        # 1 EMA crossover
        if ema9 > ema21:
            score += 1
            checks.append("EMA Bullish")
        else:
            score -= 1

        # 2 candle close
        if price > prev['Close']:
            score += 1
            checks.append("Candle Up")
        else:
            score -= 1

        # 3 RSI range
        if 45 <= rsi <= 65:
            score += 1
            checks.append("RSI Good")

        # 4 RSI filter
        if rsi < 70:
            score += 1
        else:
            score -= 1

        # 5 VWAP
        if price > vwap:
            score += 1
            checks.append("Above VWAP")
        else:
            score -= 1

        # 6 Volume
        if volume > avg_vol:
            score += 1
            checks.append("Volume High")

        # 7 Breakout
        if price > prev['High']:
            score += 2
            checks.append("Breakout Up")
        elif price < prev['Low']:
            score -= 2

        # ===== SIGNAL =====
        if score >= 5:
            signal = "CALL"
        elif score <= -5:
            signal = "PUT"
        else:
            signal = "NO TRADE"

        return signal, score, price, rsi, checks

    except:
        return None

# ================= UI =================
stock = st.text_input("Enter Stock", "RELIANCE.NS")

if stock:
    data = yf.download(stock, period="3mo", interval="1d")

    if not data.empty:
        result = analyze(data)

        if result:
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

            st.subheader("📊 Summary")
            st.write(f"Price: {price}")
            st.write(f"RSI: {rsi}")
            st.write(f"Score: {score}")
            st.write(f"Signal: {signal}")

            st.subheader("🧠 Checks Passed")
            for c in checks:
                st.write(f"✔️ {c}")

            trade = option_trade(price, signal)

            if trade:
                option, entry, target, sl = trade

                st.subheader("📊 Trade Setup")
                st.write(f"Option: {option}")
                st.write(f"Entry: {entry}")
                st.write(f"Target: {target}")
                st.write(f"SL: {sl}")

# ================= SCANNER =================
st.header("🔥 Scanner")

stocks = [
    "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS",
    "ICICIBANK.NS","SBIN.NS","ITC.NS","AXISBANK.NS"
]

rows = []

for s in stocks:
    data = yf.download(s, period="3mo", interval="1d")

    if data.empty:
        continue

    result = analyze(data)

    if result:
        signal, score, price, rsi, _ = result

        if signal != "NO TRADE":
            trade = option_trade(price, signal)

            if trade:
                option, entry, target, sl = trade

                rows.append({
                    "Stock": s,
                    "Signal": signal,
                    "Option": option,
                    "Entry": entry,
                    "Target": target,
                    "SL": sl
                })

if rows:
    df = pd.DataFrame(rows)
    st.dataframe(df)
else:
    st.write("No trades found")

st.write("⚠️ For learning purpose only")
