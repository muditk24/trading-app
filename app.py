# app.py
import streamlit as st
import yfinance as yf
import pandas as pd
import ta
from datetime import datetime, timedelta

st.set_page_config(page_title="AI Option Trading Assistant", layout="wide")
st.title("📊 AI Option Trading Assistant")

# ----- User Input -----
stock_input = st.text_input("Enter Stock (e.g. RELIANCE.NS)", value="RELIANCE.NS")

# ----- Helper Functions -----
def safe(x, default=50):
    try:
        return float(x)
    except:
        return default

def analyze(data):
    data = data.copy().dropna()
    close = pd.to_numeric(data['Close'], errors='coerce').dropna()

    # Indicators
    data['ema9'] = ta.trend.EMAIndicator(close, 9).ema_indicator()
    data['ema21'] = ta.trend.EMAIndicator(close, 21).ema_indicator()
    data['ema50'] = ta.trend.EMAIndicator(close, 50).ema_indicator()
    data['rsi'] = ta.momentum.RSIIndicator(close).rsi()
    data['supertrend'] = ta.trend.EMAIndicator(close, 10).ema_indicator()  # simplified Supertrend

    latest = data.iloc[-1]
    price = safe(latest['Close'])
    ema9 = safe(latest['ema9'])
    ema21 = safe(latest['ema21'])
    ema50 = safe(latest['ema50'])
    rsi = safe(latest['rsi'],50)

    # ----- Trading Rules Logic -----
    signal = "NO TRADE"
    strike = "ATM"

    # Basic rules (based on your rulebook)
    if price > ema9 > ema21 and rsi < 65:
        signal = "CALL"
        if rsi < 45:
            strike = "Slight ITM"
    elif price < ema9 < ema21 and rsi > 35:
        signal = "PUT"
        if rsi > 55:
            strike = "Slight ITM"

    # Prevent overbought/oversold trades
    if signal=="CALL" and rsi>70:
        signal = "NO TRADE"
    if signal=="PUT" and rsi<30:
        signal = "NO TRADE"

    return signal, price, rsi, ema9, ema21, ema50, strike

# ----- Fetch Data -----
try:
    end = datetime.now()
    start = end - timedelta(days=7)
    data = yf.download(stock_input, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), interval="15m")
    if data.empty:
        st.error("Error loading stock data")
    else:
        # ----- Analysis -----
        signal, price, rsi, ema9, ema21, ema50, strike = analyze(data)

        st.subheader(f"Latest Analysis for {stock_input}")
        st.write(f"Price: {price:.2f} | EMA9: {ema9:.2f} | EMA21: {ema21:.2f} | EMA50: {ema50:.2f} | RSI: {rsi:.2f}")
        st.write(f"✅ Suggested Trade: **{signal}** | Recommended Strike: **{strike}**")

        # ----- Simple Recommendations -----
        st.subheader("💡 Last Day Top Trades (Learning Purpose Only)")
        last_day = data.tail(1)
        st.write(last_day[['Open','High','Low','Close']])

        st.warning("⚠️ For learning purposes only. Do NOT trade real money blindly.")
except Exception as e:
    st.error(f"Failed to fetch data: {e}")
