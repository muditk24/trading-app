import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
import numpy as np
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime

# ================= UI SETUP =================
st.set_page_config(page_title="Pro Options Trader", layout="wide", page_icon="📈")

# ================= MASTER STOCK LIST (NIFTY 100) =================
STOCK_MAP = {
    # Heavyweights & Banks
    "RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS", "HDFC BANK": "HDFCBANK.NS", "ICICI BANK": "ICICIBANK.NS",
    "INFOSYS": "INFY.NS", "SBI": "SBIN.NS", "BHARTI AIRTEL": "BHARTIARTL.NS", "ITC": "ITC.NS",
    "L&T": "LT.NS", "BAJAJ FINANCE": "BAJFINANCE.NS", "KOTAK BANK": "KOTAKBANK.NS", "AXIS BANK": "AXISBANK.NS",
    "HCL TECH": "HCLTECH.NS", "ASIAN PAINTS": "ASIANPAINT.NS", "MARUTI": "MARUTI.NS", "SUN PHARMA": "SUNPHARMA.NS",
    "TATA MOTORS": "TATAMOTORS.NS", "ULTRATECH CEMENT": "ULTRACEMCO.NS", "NTPC": "NTPC.NS", "M&M": "M&M.NS",
    
    # Core Sectors & Favourites
    "ONGC": "ONGC.NS", "COAL INDIA": "COALINDIA.NS", "PFC": "PFC.NS", "GODREJ PROPERTIES": "GODREJPROP.NS",
    "GODREJ CONSUMER": "GODREJCP.NS", "WIPRO": "WIPRO.NS", "POWER GRID": "POWERGRID.NS", "TITAN": "TITAN.NS",
    "BAJAJ FINSERV": "BAJAJFINSV.NS", "ADANI ENTERPRISES": "ADANIENT.NS", "HINDALCO": "HINDALCO.NS", 
    "JSW STEEL": "JSWSTEEL.NS", "TATA STEEL": "TATASTEEL.NS", "GRASIM": "GRASIM.NS", "ADANI PORTS": "ADANIPORTS.NS",
    
    # Financials & Insurance
    "HDFC LIFE": "HDFCLIFE.NS", "SBI LIFE": "SBILIFE.NS", "CHOLAMANDALAM FIN": "CHOLAFIN.NS", "REC LTD": "RECLTD.NS",
    "M&M FIN": "M&MFIN.NS", "MUTHOOT FINANCE": "MUTHOOTFIN.NS", "ICICI LOMBARD": "ICICIGI.NS", 
    "ICICI PRU": "ICICIPRULI.NS", "SBI CARD": "SBICARD.NS", "BAJAJ AUTO": "BAJAJ-AUTO.NS",
    
    # Pharma, FMCG & Auto
    "APOLLO HOSPITALS": "APOLLOHOSP.NS", "DR REDDY": "DRREDDY.NS", "DIVIS LAB": "DIVISLAB.NS", "CIPLA": "CIPLA.NS",
    "TORNADO PHARMA": "TORNTPHARM.NS", "LUPIN": "LUPIN.NS", "AUROBINDO PHARMA": "AUROPHARMA.NS",
    "BIOCON": "BIOCON.NS", "NESTLE": "NESTLEIND.NS", "BRITANNIA": "BRITANNIA.NS", "TATA CONSUMER": "TATACONSUM.NS",
    "HUL": "HINDUNILVR.NS", "DABUR": "DABUR.NS", "MARICO": "MARICO.NS", "COLGATE": "COLPAL.NS",
    "EICHER MOTORS": "EICHERMOT.NS", "HERO MOTOCORP": "HEROMOTOCO.NS", "TVS MOTOR": "TVSMOTOR.NS",
    "ASHOK LEYLAND": "ASHOKLEY.NS", "ESCORTS": "ESCORTS.NS", "MRF": "MRF.NS", "BOSCH": "BOSCHLTD.NS",
    
    # Tech, Defense & Others
    "LTIMINDTREE": "LTIM.NS", "TECH MAHINDRA": "TECHM.NS", "PERSISTENT": "PERSISTENT.NS", "COFORGE": "COFORGE.NS",
    "MPHASIS": "MPHASIS.NS", "TATA COMM": "TATACOMM.NS", "BEL": "BEL.NS", "HAL": "HAL.NS", "ZOMATO": "ZOMATO.NS",
    "INDIGO": "INDIGO.NS", "TRENT": "TRENT.NS", "VEDANTA": "VEDL.NS", "GAIL": "GAIL.NS", "PNB": "PNB.NS",
    "BANK OF BARODA": "BANKBARODA.NS", "CANARA BANK": "CANBK.NS", "INDUSIND BANK": "INDUSINDBK.NS",
    "AU SMALL FINANCE": "AUBANK.NS", "BANDHAN BANK": "BANDHANBNK.NS", "IDFC FIRST BANK": "IDFCFIRSTB.NS",
    "HAVELLS": "HAVELLS.NS", "POLYCAB": "POLYCAB.NS", "CUMMINS": "CUMMINSIND.NS", "BHEL": "BHEL.NS",
    "SRF": "SRF.NS", "PI INDUSTRIES": "PIIND.NS", "BERGE PAINT": "BERGEPAINT.NS", "UPL": "UPL.NS",
    "BHARAT FORGE": "BHARATFORG.NS", "PAGE INDUSTRIES": "PAGEIND.NS", "DIXON": "DIXON.NS"
}

# ================= HELPER FUNCTIONS =================
def safe_float(val, default=0):
    try: return float(val)
    except: return default

def analyze_sentiment(headline):
    text = str(headline).lower()
    positive_words = ['surges', 'jumps', 'gains', 'profit', 'growth', 'buy', 'bullish', 'record', 'dividend', 'wins', 'order', 'up', 'high', 'soars', 'approves', 'positive']
    negative_words = ['falls', 'drops', 'loss', 'declines', 'sell', 'bearish', 'misses', 'downgrade', 'penalty', 'crash', 'slips', 'down', 'low', 'plummets', 'weak', 'negative', 'resigns']
    
    pos_count = sum(1 for word in positive_words if word in text)
    neg_count = sum(1 for word in negative_words if word in text)
    
    if pos_count > neg_count: return "🟢 Positive"
    elif neg_count > pos_count: return "🔴 Negative"
    else: return "⚪ Neutral"

def get_indian_news(company_name):
    # Exact quotes aur 'share market news' lagaya gaya hai 100% accuracy ke liye
    search_term = f'"{company_name}" share market news'
    query = urllib.parse.quote(search_term)
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
        
        root = ET.fromstring(xml_data)
        news_items = []
        
        # Top 3 latest exact match news
        for item in root.findall('.//item')[:3]: 
            title = item.find('title').text
            link = item.find('link').text
            clean_title = title.rsplit(' - ', 1)[0] if ' - ' in title else title
            news_items.append({'title': clean_title, 'link': link})
            
        return news_items
    except Exception as e:
        return []

# ================= CUSTOM INDICATORS =================
def calculate_vwap(df):
    df = df.copy()
    df['Date'] = pd.to_datetime(df.index).date
    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    if df['Volume'].sum() == 0: return df['Typical_Price']
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

# ================= ANALYSIS (9 RULES LOGIC) =================
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

        if volume == 0 or pd.isna(volume): is_index = True

        call_score = 0; put_score = 0; reasons = []

        # --- CALL RULES ---
        if ema9 > ema21 and price > ema9 and price > open_price: call_score += 2; reasons.append("EMA 9>21 & Closed Above")
        if supertrend_green: call_score += 1; reasons.append("Supertrend is Green")
        if 45 <= rsi <= 65: call_score += 1; reasons.append(f"RSI optimal ({round(rsi,1)})")
        elif rsi < 70: call_score += 0.5 
        if not is_index:
            if price > vwap: call_score += 1; reasons.append("Price > VWAP")
            if volume > avg_vol: call_score += 1; reasons.append("Volume Spike")

        # --- PUT RULES ---
        if ema9 < ema21 and price < ema9 and price < open_price: put_score += 2; reasons.append("EMA 9<21 & Closed Below")
        if not supertrend_green: put_score += 1; reasons.append("Supertrend is Red")
        if 35 <= rsi <= 55: put_score += 1; reasons.append(f"RSI optimal ({round(rsi,1)})")
        elif rsi > 30: put_score += 0.5
        if not is_index:
            if price < vwap: put_score += 1; reasons.append("Price < VWAP")
            if volume > avg_vol: put_score += 1; reasons.append("Volume Spike")

        signal = "⚪ NO TRADE"; final_score = 0
        passing_score = 3.5 if is_index else 5
        
        if call_score >= passing_score:
            signal = "🟢 STRONG CALL" if call_score >= (passing_score + 1) else "🟢 CALL"
            final_score = call_score
        elif put_score >= passing_score:
            signal = "🔴 STRONG PUT" if put_score >= (passing_score + 1) else "🔴 PUT"
            final_score = put_score
        else: reasons = ["Setup not matching enough rules"]

        return signal, final_score, price, round(rsi, 2), reasons
    except Exception as e: return None

# ================= UI LAYOUT =================
st.title("📊 AI Option Trading Assistant (Pro Detailed)")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Single Stock Analysis", "📈 Nifty & BankNifty", "🔥 Top 10 Scanner", "📰 Live Indian News"])

# ---------- TAB 1: SINGLE STOCK ----------
with tab1:
    dropdown_options = list(STOCK_MAP.keys()) + ["➕ OTHER (Type Custom Symbol)"]
    selected_name = st.selectbox("🔍 Select a Stock to Analyze:", options=dropdown_options)

    stock_symbol = None
    if selected_name == "➕ OTHER (Type Custom Symbol)":
        custom_input = st.text_input("Enter exact NSE Symbol (e.g., ZOMATO):").upper().strip()
        if custom_input: stock_symbol = custom_input if custom_input.endswith(".NS") else f"{custom_input}.NS"
    else: stock_symbol = STOCK_MAP[selected_name]

    if stock_symbol:
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
                    fig = go.Figure(data=[go.Candlestick(x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="Price")])
                    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=400)
                    st.plotly_chart(fig, use_container_width=True)

                with c2:
                    st.subheader("🧠 Rulebook Checklist")
                    for r in reasons: st.write(f"✔️ {r}")
                    trade = option_trade(stock_symbol, price, signal)
                    if trade and "NO TRADE" not in signal:
                        st.markdown("### 🎯 Trade Setup")
                        option, entry, target, sl = trade
                        st.info(f"**Strike to Buy:** ATM or 1 OTM ({option})")
                        st.success(f"**Target:** ₹{target}")
                        st.error(f"**SL:** ₹{sl}")
        else: st.error(f"❌ Data not found for {stock_symbol}.")

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
                    if "CALL" in signal: st.success(signal)
                    elif "PUT" in signal: st.error(signal)
                    else: st.warning(signal)
                    if "NO TRADE" not in signal:
                        trade = option_trade(symbol, price, signal)
                        if trade: st.info(f"**Strike:** {trade[0]}")
            else: st.write("Data not available right now.")

# ---------- TAB 3: TOP 10 SCANNER ----------
with tab3:
    st.header("⚡ Top 10 Stocks Scanner (15m Intraday)")
    st.write("Scanning Nifty 100 stocks for the best setups. Please wait for the scan to finish.")
    scan_list = list(STOCK_MAP.keys())

    if st.button("Start Top 10 Scan 🚀"):
        rows = []
        progress_bar = st.progress(0)
        
        for i, name in enumerate(scan_list):
            progress_bar.progress((i + 1) / len(scan_list))
            symbol = STOCK_MAP[name]
            data = yf.Ticker(symbol).history(period="5d", interval="15m")
            if not data.empty:
                result = analyze_stock(data)
                if result:
                    signal, score, price, rsi, _ = result
                    if "NO TRADE" not in signal:
                        trade = option_trade(symbol, price, signal)
                        if trade:
                            rows.append({"Stock Name": name, "Signal": signal, "Score": score, "Option": trade[0], "RSI": rsi})

        if rows:
            df = pd.DataFrame(rows).sort_values(by="Score", ascending=False).head(10)
            df.index = np.arange(1, len(df) + 1)
            st.dataframe(df.style.map(lambda x: 'color: green' if 'CALL' in str(x) else ('color: red' if 'PUT' in str(x) else ''), subset=['Signal']), use_container_width=True)
        else: st.warning("Koi solid intraday setup nahi mila. Market range-bound hai.")

# ---------- TAB 4: LIVE INDIAN NEWS & SENTIMENT + TECH ALIGNMENT ----------
with tab4:
    st.header("📰 Live Indian Market News + Technical Alignment")
    st.write("Fetching real-time news directly from Indian Financial Portals and aligning with Tech Signals...")
    
    top_15_leaders = [
        "RELIANCE", "HDFC BANK", "TCS", "INFOSYS", "ICICI BANK", 
        "SBI", "ITC", "L&T", "BHARTI AIRTEL", "KOTAK BANK",
        "AXIS BANK", "TATA MOTORS", "M&M", "MARUTI", "BAJAJ FINANCE"
    ]

    if st.button("Fetch Live News & Align Tech 🚀"):
        news_rows = []
        news_progress = st.progress(0)
        
        for i, name in enumerate(top_15_leaders):
            news_progress.progress((i + 1) / len(top_15_leaders))
            symbol = STOCK_MAP[name]
            
            try:
                # 1. Fetching LIVE Indian News via exact match
                live_news = get_indian_news(name)
                
                # 2. Fetching Technical Data
                data = yf.Ticker(symbol).history(period="5d", interval="15m")
                tech_signal = "⚪ NO TRADE"
                option_detail = "-"
                
                # 3. Applying your 9-Rule Logic
                if not data.empty:
                    result = analyze_stock(data)
                    if result:
                        signal, score, price, rsi, _ = result
                        tech_signal = signal
                        
                        if "NO TRADE" not in signal:
                            trade = option_trade(symbol, price, signal)
                            if trade:
                                option_detail = f"{trade[0]} | TGT: {trade[2]} | SL: {trade[3]}"
                
                # 4. Combining News with Technical Setup
                if live_news:
                    for item in live_news: 
                        headline = item['title']
                        link = item['link']
                        sentiment = analyze_sentiment(headline)
                        
                        news_rows.append({
                            "Stock": name,
                            "Tech Signal": tech_signal,
                            "News Sentiment": sentiment,
                            "Trade Setup": option_detail,
                            "Headline": headline,
                            "Link": link
                        })
            except Exception as e:
                continue
                
        if news_rows:
            news_df = pd.DataFrame(news_rows)
            st.dataframe(
                news_df.style.map(lambda x: 'color: green' if 'CALL' in str(x) else ('color: red' if 'PUT' in str(x) else ''), subset=['Tech Signal']),
                column_config={
                    "Link": st.column_config.LinkColumn("Read Article"),
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("No major news updates available at this moment.")
