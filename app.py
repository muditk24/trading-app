# ---------- TAB 4: NEWS & SENTIMENT + TECH ALIGNMENT ----------
with tab4:
    st.header("📰 Live Market News + Technical Alignment")
    st.write("Finding deadly combos: Combining latest news sentiment with your 15m Technical Rulebook...")
    
    top_15_leaders = [
        "RELIANCE", "HDFC BANK", "TCS", "INFOSYS", "ICICI BANK", 
        "SBI", "ITC", "L&T", "BHARTI AIRTEL", "KOTAK BANK",
        "AXIS BANK", "TATA MOTORS", "M&M", "MARUTI", "BAJAJ FINANCE"
    ]

    if st.button("Fetch News & Align Tech 🚀"):
        news_rows = []
        news_progress = st.progress(0)
        
        for i, name in enumerate(top_15_leaders):
            news_progress.progress((i + 1) / len(top_15_leaders))
            symbol = STOCK_MAP[name]
            
            try:
                # 1. Fetching News
                ticker = yf.Ticker(symbol)
                news_data = ticker.news
                
                # 2. Fetching Technical Data
                data = ticker.history(period="5d", interval="15m")
                tech_signal = "⚪ NO TRADE"
                option_detail = "-"
                
                # 3. Applying your 9-Rule Logic
                if not data.empty:
                    result = analyze_stock(data)
                    if result:
                        signal, score, price, rsi, _ = result
                        tech_signal = signal
                        
                        # Generate Entry, Target, SL if trade is valid
                        if "NO TRADE" not in signal:
                            trade = option_trade(symbol, price, signal)
                            if trade:
                                # trade format: (Option, Entry, Target, SL)
                                option_detail = f"{trade[0]} | TGT: {trade[2]} | SL: {trade[3]}"
                
                # 4. Combining News with Technical Setup
                if news_data:
                    for item in news_data[:2]: # Taking top 2 latest news per stock
                        headline = item.get("title", "")
                        link = item.get("link", "")
                        
                        # AI Sentiment Logic
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
            
            # Styling technical signals with Green/Red for easy spotting
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
