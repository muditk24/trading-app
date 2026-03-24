import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go

# ================= UI SETUP =================
st.set_page_config(page_title="Alpha Pro Scanner", layout="wide", page_icon="💰")
st.title("🚀 Alpha Pro: Option Scalping Dashboard")

# ================= MASTER CONFIG =================
# Added your preferred stocks to the radar
STOCK_MAP = {
    "NIFTY 50": "^NSEI", "BANK NIFTY": "^NSEBANK",
    "ONGC": "ONGC.NS", "COAL INDIA": "COALINDIA.NS", "PFC": "PFC.NS",
    "RELIANCE": "RELIANCE.NS", "HDFC BANK": "HDFCBANK.NS", "ICICI BANK": "ICICIBANK.NS",
    "SBI": "SBIN.NS", "TCS": "TCS.NS", "INFOSYS": "INFY.NS"
}

# ================= HELPER FUNCTIONS =================
def get_atm_strike(price, symbol):
    """Calculates ATM Strike based on index/stock step size"""
    if "NIFTY 50" in symbol:
        return round(price / 50) * 50
    elif "BANK NIFTY" in symbol:
        return round(price / 100) * 100
    else:
        # Generic rounding for stocks (can be adjusted per stock lot size)
        return round(price) 

def get_data_and_analyze(symbol_name, ticker):
    try:
        df = yf.Ticker(ticker).history(period="2d", interval="5m")
        if len(df) < 25: return None
        
        # Indicators
        df['EMA9'] = ta.trend.EMAIndicator(df['Close'], window=9).ema_indicator()
        df['EMA21'] = ta.trend.EMAIndicator(df['Close'], window=21).ema_indicator()
        df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
        df['Date'] = pd.to_datetime(df.index).date
        df['VWAP'] = ( ((df['High'] + df['Low'] + df['Close']) / 3) * df['Volume'] ).groupby(df['Date']).cumsum() / df['Volume'].groupby(df['Date']).cumsum()

        curr = df.iloc[-1]
        price = round(curr['Close'], 2)
        rsi = round(curr['RSI'], 1)
        atm = get_atm_strike(price, symbol_name)
        
        # Default State
        signal = "WAITING"
        target = sl = 0
        option_type = ""
        
        # CALL Condition: Price > EMA9 > EMA21 & Price > VWAP & RSI > 55
        if curr['EMA9'] > curr['EMA21'] and price > curr['VWAP'] and rsi > 55:
            signal = "🟢 BUY CALL"
            option_type = "CE"
            sl = round(min(curr['EMA21'], price * 0.996), 2)
            target = round(price + (price - sl) * 2, 2) # 1:2 Risk Reward
        
        # PUT Condition: Price < EMA9 < EMA21 & Price < VWAP & RSI < 45
        elif curr['EMA9'] < curr['EMA21'] and price < curr['VWAP'] and rsi < 45:
            signal = "🔴 BUY PUT"
            option_type = "PE"
            sl = round(max(curr['EMA21'], price * 1.004), 2)
            target = round(price - (sl - price) * 2, 2)

        return {
            "symbol": symbol_name, "price": price, "signal": signal, 
            "strike": f"{atm} {option_type}" if option_type else "-",
            "target": target, "sl": sl, "rsi": rsi, "df": df
        }
    except Exception as e:
        return None

# ================= TABS =================
t1, t2, t3 = st.tabs(["📈 Indices (Nifty/BN)", "🎯 Recommended Options", "📊 Live Charts"])

# --- TAB 1: INDICES ---
with t1:
    st.header("⚡ Live Index Options Setup")
    idx_cols = st.columns(2)
    for i, name in enumerate(["NIFTY 50", "BANK NIFTY"]):
        res = get_data_and_analyze(name, STOCK_MAP[name])
        if res:
            with idx_cols[i]:
                st.subheader(name)
                st.metric("Current Spot Price", f"₹{res['price']}")
                
                if "BUY" in res['signal']:
                    st.success(f"**Action:** {res['signal']}")
                    
                    # Highlighted Strike Price Box
                    st.markdown(f"""
                    <div style="background-color:#2e3b4e;padding:15px;border-radius:10px;margin-bottom:15px;">
                        <h3 style="color:white;margin:0;">Recommended Strike: <span style="color:#00ffcc;">{res['strike']}</span></h3>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c1, c2 = st.columns(2)
                    c1.metric("🎯 Target (Spot)", f"₹{res['target']}")
                    c2.metric("🛡️ Stop Loss", f"₹{res['sl']}")
                else:
                    st.warning("⏳ Sideways Market. Wait for EMA 9 & 21 Crossover.")
                    st.write("**Recommended Strike:** Not generated (No setup)")
                    
                st.caption(f"RSI (14): {res['rsi']} | VWAP Support/Resist: ₹{round(res['df']['VWAP'].iloc[-1], 2)}")

# --- TAB 2: RECOMMENDED OPTIONS (The Dedicated Screener) ---
with t2:
    st.header("🎯 Live Call / Put Recommendations")
    st.write("Scanning all indices and stocks for strong momentum breakouts...")
    
    if st.button("🔄 Refresh Scanner"):
        active_trades = []
        with st.spinner("Scanning market..."):
            for name, ticker in STOCK_MAP.items():
                res = get_data_and_analyze(name, ticker)
                if res and "BUY" in res['signal']:
                    active_trades.append({
                        "Asset": name,
                        "Action": res['signal'],
                        "Recommended Strike": res['strike'],
                        "Spot Entry": res['price'],
                        "Target (Spot)": res['target'],
                        "Stop Loss (Spot)": res['sl'],
                        "RSI Strength": res['rsi']
                    })
        
        if active_trades:
            df_trades = pd.DataFrame(active_trades)
            st.dataframe(
                df_trades.style.applymap(
                    lambda x: 'background-color: rgba(0, 255, 0, 0.1); color: green; font-weight: bold;' if 'CALL' in str(x) else 
                              ('background-color: rgba(255, 0, 0, 0.1); color: red; font-weight: bold;' if 'PUT' in str(x) else ''), 
                    subset=['Action']
                ), 
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Market is currently sideways. No active 'Strong Buy/Put' signals found in the current 5-minute candle.")

# --- TAB 3: CHART ANALYSIS ---
with t3:
    st.header("📊 Advanced Technical Chart")
    sel = st.selectbox("Select Asset to view Chart:", list(STOCK_MAP.keys()))
    res = get_data_and_analyze(sel, STOCK_MAP[sel])
    
    if res:
        fig = go.Figure(data=[go.Candlestick(x=res['df'].index, open=res['df']['Open'], high=res['df']['High'], low=res['df']['Low'], close=res['df']['Close'], name="Price")])
        fig.add_trace(go.Scatter(x=res['df'].index, y=res['df']['EMA9'], line=dict(color='#00bfff', width=1.5), name="EMA 9 (Fast)"))
        fig.add_trace(go.Scatter(x=res['df'].index, y=res['df']['EMA21'], line=dict(color='#ff9900', width=1.5), name="EMA 21 (Slow)"))
        fig.add_trace(go.Scatter(x=res['df'].index, y=res['df']['VWAP'], line=dict(color='#ff00ff', width=1.5, dash='dash'), name="VWAP"))
        
        fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, title=f"{sel} - 5 Min Chart")
        st.plotly_chart(fig, use_container_width=True)
