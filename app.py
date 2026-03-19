import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("📊 AI Option Trading Assistant (Pro Detailed)")

# ================= SAFE FLOAT =================
def safe_float(val, default=0):
    try:
        return float(val)
    except:
        return default

# ================= OPTION LOGIC =================
def option_trade(price, signal):
    strike = round(price / 50) * 50

    if "CALL" in signal:
        return f"{strike} CE", price, round(price*1.02,2), round(price*0.99,2)
    elif "PUT" in signal:
        return f"{strike} PE", price, round(price*0.98,2), round(price*1.01,2)
    return None

# ================= ANALYSIS =================
def analyze_stock(data):
    try:
        data = data.copy()
        data.dropna(inplace=True)

        if len(data) < 50:
            return None

        close = data['Close'].squeeze()

        # Indicators
        data['ema20'] = ta.trend.EMAIndicator(close, window=20).ema_indicator()
        data['ema50'] = ta.trend.EMAIndicator(close, window=50).ema_indicator()
        data['rsi'] = ta.momentum.RSIIndicator(close).rsi()

        macd = ta.trend.MACD(close)
        data['macd'] = macd.macd()
        data['macd_signal'] = macd.macd_signal()

        adx = ta.trend.ADXIndicator(data['High'], data['Low'], data['Close'])
        data['adx'] = adx.adx()

        latest = data.iloc[-1]
        prev = data.iloc[-2]

        price = safe_float(latest['Close'])
        prev_close = safe_float(prev['Close'])

        ema20 = safe_float(latest['ema20'], price)
        ema50 = safe_float(latest['ema50'], price)
        rsi = safe_float(latest['rsi'], 50)
        macd_val = safe_float(latest['macd'])
        macd_signal = safe_float(latest['macd_signal'])
        adx_val = safe_float(latest['adx'])

        volume = safe_float(latest['Volume'])
        avg_volume = safe_float(data['Volume'].mean())

        score = 0
        reasons = []

        # ===== RULES =====
        if price > ema50:
            score += 1
            reasons.append("Price > EMA50")
        else:
            score -= 1

        if ema20 > ema50:
            score += 1
            reasons.append("EMA20 > EMA50")

        if price > ema20:
            score += 1
            reasons.append("Price > EMA20")

        if rsi < 30:
            score += 2
            reasons.append("RSI Oversold")
        elif rsi < 40:
            score += 1
            reasons.append("RSI Low")
        elif rsi > 70:
            score -= 2
            reasons.append("RSI Overbought")

        if macd_val > macd_signal:
            score += 1
            reasons.append("MACD Bullish")
        else:
            score -= 1

        if volume > avg_volume:
            score += 1
            reasons.append("High Volume")

        if volume > 1.5 * avg_volume:
            score += 1
            reasons.append("Volume Spike")

        if price > prev_close:
            score += 1
            reasons.append("Price Up")
        else:
            score -= 1

        if price > prev['High']:
            score += 2
            reasons.append("Breakout Up")
        elif price < prev['Low']:
            score -= 2
            reasons.append("Breakout Down")

        if adx_val > 25:
            score += 1
            reasons.append("Strong Trend")

        # ===== SIGNAL =====
        if score >= 6:
            signal = "🔥 STRONG CALL"
        elif score >= 3:
            signal = "CALL"
        elif score <= -6:
            signal = "🔥 STRONG PUT"
        elif score <= -3:
            signal = "PUT"
        else:
            signal = "NO TRADE"

        return signal, score, price, rsi, reasons

    except:
        return None

# ================= SINGLE STOCK =================
stock = st.text_input("Enter Stock (e.g. RELIANCE.NS)", "RELIANCE.NS")

if stock:
    data = yf.download(stock, period="3mo", interval="1d")

    if not data.empty:
        result = analyze_stock(data)

        if result:
            signal, score, price, rsi, reasons = result

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

            st.subheader("🧠 Why this signal?")
            for r in reasons:
                st.write(f"✔️ {r}")

            trade = option_trade(price, signal)

            if trade:
                option, entry, target, sl = trade

                st.subheader("📊 Trade Setup")
                st.write(f"Option: {option}")
                st.write(f"Entry: {entry}")
                st.write(f"Target: {target}")
                st.write(f"Stop Loss: {sl}")

# ================= SCANNER =================
st.header("🔥 Top Trades Scanner")

stocks = [
    "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
    "SBIN.NS","ITC.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS",
    "TATAMOTORS.NS","WIPRO.NS","HCLTECH.NS","ADANIPORTS.NS"
]

rows = []

for s in stocks:
    data = yf.download(s, period="3mo", interval="1d")

    if data.empty:
        continue

    result = analyze_stock(data)

    if result:
        signal, score, price, rsi, _ = result

        if signal != "NO TRADE":
            trade = option_trade(price, signal)

            if trade:
                option, entry, target, sl = trade

                rows.append({
                    "Stock": s,
                    "Signal": signal,
                    "Score": score,
                    "Option": option,
                    "Entry": entry,
                    "Target": target,
                    "SL": sl
                })

if rows:
    df = pd.DataFrame(rows)
    df = df.sort_values(by="Score", ascending=False)
    st.dataframe(df, use_container_width=True)
else:
    st.write("No trades found")

st.write("⚠️ For learning purpose only")
