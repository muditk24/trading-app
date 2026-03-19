import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
import numpy as np

# UI Setup
st.set_page_config(page_title="Pro Options Trader", layout="wide", page_icon="📈")

# ================= SMART DICTIONARY (GLOBAL) =================
# Ab yeh pure app mein kahin bhi kaam karega
STOCK_MAP = {
    "GODREJ PROPERTIES": "GODREJPROP",
    "GODREJ CONSUMER": "GODREJCP",
    "GODREJ": "GODREJCP", # Default godrej
    "STATE BANK OF INDIA": "SBIN",
    "SBI": "SBIN",
    "HDFC BANK": "HDFCBANK",
    "RELIANCE INDUSTRIES": "RELIANCE",
    "TATA MOTORS": "TATAMOTORS",
    "BAJAJ FINANCE": "BAJFINANCE",
    "COAL INDIA": "COALINDIA",
    "ONGC": "ONGC",
    "POWER FINANCE": "PFC",
    "PFC": "PFC",
    "TCS": "TCS",
    "INFY": "INFY"
}

def get_ticker_symbol(name):
    """Company ka naam lega aur exact Yahoo Finance symbol return karega"""
    name_upper = str(name).upper().strip()
    # Check if name is in dictionary, else use the raw name
    base_symbol = STOCK_MAP.get(name_upper, name_upper)
    
    # Agar index nahi hai aur .NS nahi laga hai, toh laga do
    if not base_symbol.endswith(".NS") and not base_symbol.startswith("^"):
        return f"{base_symbol}.NS"
    return base_symbol

# ================= SAFE FLOAT =================
def safe_float(val, default=0):
    try:
        return float(val)
    except:
        return default

# ================= CUSTOM INDICATORS =================
def calculate_vwap(df):
    df = df.copy()
    df['Date'] = pd.to_datetime(df.index).date
    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    
    if df['Volume'].sum() == 0:
        return df['Typical_Price']
        
    df['VP'] = df['Typical_Price'] * df['Volume']
    df['Cum_Vol'] = df.groupby('Date')['Volume'].cumsum()
    df['Cum_VP'] = df.groupby('Date')['VP'].cumsum()
    df['VWAP'] = df['Cum_VP'] / df['Cum_Vol']
    return df['VWAP']

def calculate_supertrend(df, period=10, multiplier=3):
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
            
            if df['InUptrend'].iloc[current] and df['Lowerband'].iloc[current] < df['Lowerband'].iloc[previous]:
                df.iloc[current, df.columns.get_loc('Lowerband')] = df['Lowerband'].iloc[previous]
            if not df['InUptrend'].iloc[current] and df['Upperband'].iloc[current] > df['Upperband'].iloc[previous]:
                df.iloc[current, df.columns.get_loc('Upperband')] = df['Upperband'].iloc[previous]
                
    return df['InUptrend'] 

# ================= OPTION LOGIC =================
def option_trade(symbol, price, signal):
    if "^NSEBANK" in symbol: step = 100
    elif "^NSEI" in symbol: step = 50
    else: step = 20

    strike = round(price / step) * step
    
    if "CALL" in signal:
        return f"{strike} CE", price, round(price*1.05, 2), round(price*0.95, 2)
    elif "PUT" in signal:
        return f"{strike} PE", price, round(price*0.95, 2), round(price*1.05, 2)
    return None

# ================= ANALYSIS =================
def analyze_stock(data, is_index=False):
    try:
        data = data.copy()
        data.dropna(inplace=True)
        if len(data) < 30: return None

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
        rsi = safe_float(latest['RSI'])
        vwap = safe_float(latest['VWAP'])
        supertrend_green = latest['Supertrend_Green']
        volume = safe_float(latest['Volume'])
        avg_vol = safe_float(latest['Avg_Vol'])

        if volume == 0 or pd.isna(volume):
            is_index = True

        call_score = 0
        put_score = 0
        reasons = []

        # --- CALL RULES ---
        if ema9 > ema21 and price > ema9 and price > open_price: 
            call_score += 2; reasons.append("EMA 9>21 & Closed Above")
        if supertrend_green: 
            call_score += 1; reasons.append("Supertrend is Green")
        if 45 <= rsi <= 65: 
            call_score += 1; reasons.append(f"RSI optimal ({round(rsi,1)})")
        elif rsi < 70:
            call_score += 0.5 
            
        if not is_index:
            if price > vwap: 
                call_score += 1; reasons.append("Price > VWAP")
            if volume > avg_vol: 
                call_score += 1; reasons.append("Volume Spike")

        # --- PUT RULES ---
        if ema9 < ema21 and price < ema9 and price < open_price: 
            put_score += 2; reasons.append("EMA 9<21 & Closed Below")
        if not supertrend_green: 
            put_score += 1; reasons.append("Supertrend is Red")
        if 35 <= rsi <= 55: 
            put_score += 1; reasons.append(f"RSI optimal ({round(rsi,1)})")
        elif rsi > 30:
            put_score += 0.5
            
        if not is_index:
            if price < vwap: 
                put_score += 1; reasons.append("Price < VWAP")
            if volume > avg_vol: 
                put_score += 1; reasons.append("Volume Spike")

        signal = "⚪ NO TRADE"
        final_score = 0
        passing_score = 3.5 if is_index else 5
        
        if call_score >= passing_score:
            signal = "🟢 STRONG CALL" if call_score >= (passing_score + 1) else "🟢 CALL"
            final_score = call_score
        elif put_score >= passing_score:
            signal = "🔴 STRONG PUT" if put_score >= (passing_score + 1) else "🔴 PUT"
            final_score = put_score
        else:
            reasons = ["Setup not matching enough rules"]

        return signal, final_score, price, round(rsi, 2), reasons
    except Exception as e:
        return None

# ================= UI LAYOUT =================
st.title("📊 AI Option Trading Assistant (Pro Detailed)")

tab1, tab2, tab3 = st.tabs(["📊 Single Stock Analysis", "📈 Nifty & BankNifty Setup", "🔥 Top 10 Stocks Scanner"])

# ---------- TAB 1: SINGLE STOCK ----------
with tab1:
    user_input = st.text_input("🔍 Search Any Stock (Name or Symbol):", "Godrej Properties")

    # Global function use kiya
    stock_symbol = get_ticker_symbol(user_input)

    st.header(f"Intraday Analysis (15m) for {stock_symbol.replace('.NS', '')}")
    
    with st.spinner('Fetching 15m intraday data...'):
        data = yf.Ticker(stock_symbol).history(period="5d", interval="15m")

    if not data.empty:
        result = analyze_stock(data)
        if result:
            signal, score, price, rsi, reasons = result
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Current Price", f"₹{price}")
            col2.metric("RSI", rsi)
            col3.metric("Rule Score", score)
            
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
                
                trade = option_trade(stock_symbol, price, signal)
                if trade and "NO TRADE" not in signal:
                    st.markdown("### 🎯 Trade Setup")
                    option, entry, target, sl = trade
                    st.info(f"**Strike to Buy:** ATM or 1 OTM ({option})")
                    st.success(f"**Target:** ₹{target}")
                    st.error(f"**SL:** ₹{sl}")
    else:
        st.error(f"❌ Data not found. Check spelling or ensure the symbol is correct.")

# ---------- TAB 2: INDICES ----------
with tab2:
    st.header("📈 Major Indices Scanner (15m)")
    indices = {"NIFTY 50": "^NSEI", "BANK NIFTY": "^NSEBANK"}
    cols = st.columns(len(indices))
    
    for idx, (name, symbol) in enumerate(indices.items()):
        with cols[idx]:
            st.subheader(name)
            data = yf.Ticker(symbol).history(period="5d", interval="15m")
            
            if not data.empty:
                result = analyze_stock(data, is_index=True)
                if result:
                    signal, score, price, rsi, reasons = result
                    st.metric("LTP", f"₹{price}")
                    st.write(f"**RSI:** {rsi}")
                    
                    if "CALL" in signal: st.success(signal)
                    elif "PUT" in signal: st.error(signal)
                    else: st.warning(signal)
                    
                    if "NO TRADE" not in signal:
                        trade = option_trade(symbol, price, signal)
                        if trade:
                            option, entry, target, sl = trade
                            st.info(f"**Strike:** {option}")
                            
                    st.markdown("**Reasons:**")
                    for r in reasons:
                        st.caption(f"✔️ {r}")
            else:
                st.write("Data not available right now.")

# ---------- TAB 3: TOP 10 SCANNER ----------
with tab3:
    st.header("⚡ Top 10 Stocks Scanner (15m Intraday)")
    
    # Ab aap yahan direct company ka naam bhi likh sakte hain dictionary ki wajah se
    scan_list = [
        "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "SBI", 
        "Godrej Properties", "ONGC", "Coal India", "PFC", "ITC", 
        "LT", "BAJFINANCE", "HCLTECH", "ASIANPAINT", "AXISBANK", 
        "MARUTI", "SUNPHARMA", "KOTAKBANK", "TATAMOTORS"
    ]

    if st.button("Start Top 10 Scan 🚀"):
        rows = []
        progress_bar = st.progress(0)
        
        for i, s in enumerate(scan_list):
            progress_bar.progress((i + 1) / len(scan_list))
            
            # Global function automatically map kar lega naam ko symbol se
            symbol = get_ticker_symbol(s)
            data = yf.Ticker(symbol).history(period="5d", interval="15m")
            
            if not data.empty:
                result = analyze_stock(data)
                if result:
                    signal, score, price, rsi, _ = result
                    if "NO TRADE" not in signal:
                        trade = option_trade(symbol, price, signal)
                        if trade:
                            option, entry, target, sl = trade
                            rows.append({
                                "Stock": s.upper(),
                                "Signal": signal,
                                "Score": score,
                                "Option": option,
                                "RSI": rsi
                            })

        if rows:
            df = pd.DataFrame(rows)
            df = df.sort_values(by="Score", ascending=False).head(10)
            df.index = np.arange(1, len(df) + 1)
            
            st.dataframe(
                df.style.map(lambda x: 'color: green' if 'CALL' in str(x) else ('color: red' if 'PUT' in str(x) else ''), subset=['Signal']),
                use_container_width=True
            )
        else:
            st.warning("Koi solid intraday setup nahi mila. Market range-bound hai.")
