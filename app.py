import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
import numpy as np

# UI Setup
st.set_page_config(page_title="Pro Options Trader", layout="wide", page_icon="📈")

# ================= SAFE FLOAT =================
def safe_float(val, default=0):
    try:
        return float(val)
    except:
        return default

# ================= CUSTOM INDICATORS =================
def calculate_vwap(df):
    """Calculates Intraday VWAP"""
    # Create a copy to avoid SettingWithCopyWarning
    df = df.copy()
    # Ensure timezone-aware datetime index is converted properly to extract date
    df['Date'] = pd.to_datetime(df.index).date
    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VP'] = df['Typical_Price'] * df['Volume']
    
    # Calculate cumulative values per day
    df['Cum_Vol'] = df.groupby('Date')['Volume'].cumsum()
    df['Cum_VP'] = df.groupby('Date')['VP'].cumsum()
    df['VWAP'] = df['Cum_VP'] / df['Cum_Vol']
    return df['VWAP']

def calculate_supertrend(df, period=10, multiplier=3):
    """Calculates Supertrend (Green/Red)"""
    df = df.copy()
    hl2 = (df['High'] + df['Low']) / 2
    df['ATR'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=period).average_true_range()
    
    df['Upperband'] = hl2 + (multiplier * df['ATR'])
    df['Lowerband'] = hl2 - (multiplier * df['ATR'])
    df['InUptrend'] = True

    for current in range(1, len(df.index)):
        previous = current - 1
        if df['Close'].iloc[current] > df['Upperband'].iloc[previous]:
            df.iloc[current, df.columns.get_loc('InUptrend')] = True
        elif df['Close'].iloc[current] < df['Lowerband'].iloc[previous]:
            df.iloc[current, df.columns.get_loc('InUptrend')] = False
        else:
            df.iloc[current, df.columns.get_loc('InUptrend')] = df.iloc[previous, df.columns.get_loc('InUptrend')]
            
            # Adjust bands
            if df['InUptrend'].iloc[current] and df['Lowerband'].iloc[current] < df['Lowerband'].iloc[previous]:
                df.iloc[current, df.columns.get_loc('Lowerband')] = df['Lowerband'].iloc[previous]
            if not df['InUptrend'].iloc[current] and df['Upperband'].iloc[current] > df['Upperband'].iloc[previous]:
                df.iloc[current, df.columns.get_loc('Upperband')] = df['Upperband'].iloc[previous]
                
    return df['InUptrend'] # True = Green (Bullish), False = Red (Bearish)

# ================= OPTION LOGIC =================
def option_trade(price, signal):
    strike = round(price / 50) * 50
    if "CALL" in signal:
        return f"{strike} CE", price, round(price*1.05, 2), round(price*0.95, 2)
    elif "PUT" in signal:
        return f"{strike} PE", price, round(price*0.95, 2), round(price*1.05, 2)
    return None

# ================= ANALYSIS (BASED ON RULEBOOK) =================
def analyze_stock(data):
    try:
        data = data.copy()
        data.dropna(inplace=True)
        if len(data) < 30: return None

        # Add indicators
        close = data['Close']
        data['EMA9'] = ta.trend.EMAIndicator(close, window=9).ema_indicator()
        data['EMA21'] = ta.trend.EMAIndicator(close, window=21).ema_indicator()
        data['RSI'] = ta.momentum.RSIIndicator(close, window=14).rsi()
        data['VWAP'] = calculate_vwap(data)
        data['Supertrend_Green'] = calculate_supertrend(data, 10, 3)
        data['Avg_Vol'] = data['Volume'].rolling(window=20).mean()

        latest = data.iloc[-1]
        prev = data.iloc[-2]

        price = safe_float(latest['Close'])
        open_price = safe_float(latest['Open'])
        
        ema9 = safe_float(latest['EMA9'])
        ema21 = safe_float(latest['EMA21'])
        prev_ema9 = safe_float(prev['EMA9'])
        prev_ema21 = safe_float(prev['EMA21'])
        
        rsi = safe_float(latest['RSI'])
        vwap = safe_float(latest['VWAP'])
        supertrend_green = latest['Supertrend_Green']
        
        volume = safe_float(latest['Volume'])
        avg_vol = safe_float(latest['Avg_Vol'])

        # Rule Checks (Max Score = 7 for technical setup)
        call_score = 0
        put_score = 0
        reasons = []

        # --- CALL RULES ---
        # 1 & 2. EMA 9 crossed above 21 & Candle closed above
        if ema9 > ema21 and price > ema9 and price > open_price: 
            call_score += 2; reasons.append("EMA 9>21 & Closed Above")
        # 3. Supertrend Green
        if supertrend_green: 
            call_score += 1; reasons.append("Supertrend is Green")
        # 4 & 5. RSI between 45-65 & Below 70
        if 45 <= rsi <= 65: 
            call_score += 1; reasons.append(f"RSI optimal ({round(rsi,1)})")
        elif rsi < 70:
            call_score += 0.5 # Partial point if not optimal but safe
        # 6. Price above VWAP
        if price > vwap: 
            call_score += 1; reasons.append("Price > VWAP")
        # 7. Volume above average
        if volume > avg_vol: 
            call_score += 1; reasons.append("Volume Spike")

        # --- PUT RULES ---
        # 1 & 2. EMA 9 crossed below 21 & Candle closed below
        if ema9 < ema21 and price < ema9 and price < open_price: 
            put_score += 2; reasons.append("EMA 9<21 & Closed Below")
        # 3. Supertrend Red
        if not supertrend_green: 
            put_score += 1; reasons.append("Supertrend is Red")
        # 4 & 5. RSI between 35-55 & Above 30
        if 35 <= rsi <= 55: 
            put_score += 1; reasons.append(f"RSI optimal ({round(rsi,1)})")
        elif rsi > 30:
            put_score += 0.5
        # 6. Price below VWAP
        if price < vwap: 
            put_score += 1; reasons.append("Price < VWAP")
        # 7. Volume above average
        if volume > avg_vol: 
            put_score += 1; reasons.append("Volume Spike")

        # Decide Signal
        signal = "⚪ NO TRADE"
        final_score = 0
        
        # We need at least 5 points out of 7 for a valid trade setup
        if call_score >= 5:
            signal = "🟢 STRONG CALL" if call_score >= 6 else "🟢 CALL"
            final_score = call_score
        elif put_score >= 5:
            signal = "🔴 STRONG PUT" if put_score >= 6 else "🔴 PUT"
            final_score = put_score
        else:
            reasons = ["Setup not matching all 7 rules"]

        return signal, final_score, price, round(rsi, 2), reasons
    except Exception as e:
        return None

# ================= UI LAYOUT =================
st.sidebar.title("⚙️ Control Panel")
user_input = st.sidebar.text_input("Search Any Stock:", "RELIANCE").upper().strip()

if not user_input.endswith(".NS"): stock_symbol = user_input + ".NS"
else: stock_symbol = user_input

tab1, tab2 = st.tabs(["📊 Single Stock Analysis", "🔥 Top 5 Scanner"])

with tab1:
    st.header(f"Intraday Analysis (15m) for {stock_symbol.replace('.NS', '')}")
    
    with st.spinner('Fetching 15m intraday data...'):
        # Fetched 5 days of 15m data for accurate VWAP and EMAs
        data = yf.Ticker(stock_symbol).history(period="5d", interval="15m")

    if not data.empty:
        result = analyze_stock(data)

        if result:
            signal, score, price, rsi, reasons = result

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Current Price", f"₹{price}")
            col2.metric("RSI", rsi)
            col3.metric("Rule Score (Out of 7)", score)
            
            if "CALL" in signal: col4.success(signal)
            elif "PUT" in signal: col4.error(signal)
            else: col4.warning(signal)

            st.markdown("---")
            c1, c2 = st.columns([2, 1])
            with c1:
                fig = go.Figure(data=[go.Candlestick(
                    x=data.index, open=data['Open'], high=data['High'],
                    low=data['Low'], close=data['Close'], name="Price"
                )])
                fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=400)
                st.plotly_chart(fig, use_container_width=True)

            with c2:
                st.subheader("🧠 Rulebook Checklist")
                for r in reasons:
                    st.write(f"✔️ {r}")
                
                trade = option_trade(price, signal)
                if trade and "NO TRADE" not in signal:
                    st.markdown("### 🎯 Trade Setup")
                    option, entry, target, sl = trade
                    st.info(f"**Strike to Buy:** ATM or 1 OTM ({option})")
                    st.success(f"**Target:** ₹{target}")
                    st.error(f"**SL:** ₹{sl}")
    else:
        st.error(f"Could not fetch intraday data for {stock_symbol}.")

with tab2:
    st.header("⚡ Top 5 Trades Scanner (15m Intraday)")
    st.write("Scanning Nifty 50 stocks based on your 9-Step Rulebook...")

    nifty_50 = [
        "RELIANCE","TCS","HDFCBANK","ICICIBANK","INFY","SBIN","BHARTIARTL",
        "ITC","LT","BAJFINANCE","HCLTECH","ASIANPAINT","AXISBANK","MARUTI",
        "SUNPHARMA","KOTAKBANK","TITAN","TATAMOTORS","ULTRACEMCO","NTPC"
    ]

    if st.button("Start Scan 🚀"):
        rows = []
        progress_bar = st.progress(0)
        
        for i, s in enumerate(nifty_50):
            progress_bar.progress((i + 1) / len(nifty_50))
            
            symbol = f"{s}.NS"
            # 15 min timeframe is best for this specific setup
            data = yf.Ticker(symbol).history(period="5d", interval="15m")
            
            if not data.empty:
                result = analyze_stock(data)
                if result:
                    signal, score, price, rsi, _ = result
                    if "NO TRADE" not in signal:
                        trade = option_trade(price, signal)
                        if trade:
                            option, entry, target, sl = trade
                            rows.append({
                                "Stock": s,
                                "Signal": signal,
                                "Score": score,
                                "Option": option,
                                "RSI": rsi
                            })

        if rows:
            df = pd.DataFrame(rows)
            # Sort by score and take TOP 5 ONLY
            df = df.sort_values(by="Score", ascending=False).head(5)
            
            # Reset index so it looks clean (1 to 5)
            df.index = np.arange(1, len(df) + 1)
            
            st.dataframe(
                df.style.map(lambda x: 'color: green' if 'CALL' in str(x) else ('color: red' if 'PUT' in str(x) else ''), subset=['Signal']),
                use_container_width=True
            )
        else:
            st.warning("Koi solid intraday setup nahi mila. Market range-bound ya rules fulfill nahi ho rahe.")


