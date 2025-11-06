import streamlit as st
import pandas as pd
import time
from tradingview_screener import Query, Column
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import webbrowser
import numpy as np
import requests
import random
from typing import List, Dict, Tuple
import re
import call_groq_api, escape_markdown_latex
import yfinance as yf
import ta
import feedparser
from urllib.parse import quote

# SEZIONE 1: FORMATTAZIONE (TAB 1 e 2 - INVARIATA)
def format_technical_rating(rating: float) -> str:
    if pd.isna(rating): return 'N/A'
    elif rating >= 0.5: return '🟢 Strong Buy'
    elif rating >= 0.1: return '🟢 Buy'
    elif rating >= -0.1: return '🟡 Neutral'
    elif rating >= -0.5: return '🔴 Sell'
    else: return '🔴 Strong Sell'

def format_currency(value, currency='$'):
    if pd.isna(value) or value is None: return "N/A"
    if value >= 1e12: return f"{currency}{value/1e12:.2f}T"
    elif value >= 1e9: return f"{currency}{value/1e9:.2f}B"
    elif value >= 1e6: return f"{currency}{value/1e6:.2f}M"
    else: return f"{currency}{value:.2f}"

def format_percentage(value):
    if pd.isna(value): return "N/A"
    return f"{value*100:.2f}%"

# SEZIONE 2: TRADINGVIEW (TAB 1 e 2 - INVARIATA)
def calculate_investment_score(df):
    scored_df = df.copy()
    scored_df['Investment_Score'] = 0.0
    def rsi_score(rsi):
        if pd.isna(rsi): return 0
        if 50 <= rsi <= 70: return 10
        elif 40 <= rsi < 50: return 7
        elif 30 <= rsi < 40: return 5
        elif rsi > 80: return 2
        else: return 1
    scored_df['RSI_Score'] = scored_df['RSI'].apply(rsi_score)
    scored_df['Investment_Score'] += scored_df['RSI_Score'] * 0.20
    def macd_score(macd, signal):
        if pd.isna(macd) or pd.isna(signal): return 0
        diff = macd - signal
        if diff > 0.05: return 10
        elif diff > 0: return 7
        elif diff > -0.05: return 4
        else: return 1
    scored_df['MACD_Score'] = scored_df.apply(lambda row: macd_score(row.get('MACD.macd', None) if 'MACD.macd' in row.index else row.get('macd', None), row.get('MACD.signal', None) if 'MACD.signal' in row.index else row.get('signal', None)), axis=1)
    scored_df['Investment_Score'] += scored_df['MACD_Score'] * 0.15
    def trend_score(price, sma50, sma200):
        if pd.isna(price) or pd.isna(sma50) or pd.isna(sma200): return 0
        score = 0
        if price > sma50: score += 5
        if price > sma200: score += 3
        if sma50 > sma200: score += 2
        return score
    scored_df['Trend_Score'] = scored_df.apply(lambda row: trend_score(row['close'], row['SMA50'], row['SMA200']), axis=1)
    scored_df['Investment_Score'] += scored_df['Trend_Score'] * 0.25
    def tech_rating_score(rating):
        if pd.isna(rating): return 0
        if rating >= 0.5: return 10
        elif rating >= 0.3: return 8
        elif rating >= 0.1: return 6
        elif rating >= -0.1: return 4
        else: return 2
    scored_df['Tech_Rating_Score'] = scored_df['Recommend.All'].apply(tech_rating_score)
    scored_df['Investment_Score'] += scored_df['Tech_Rating_Score'] * 0.20
    def volatility_score(vol):
        if pd.isna(vol): return 0
        if 0.5 <= vol <= 2.0: return 10
        elif 0.3 <= vol < 0.5: return 7
        elif 2.0 < vol <= 3.0: return 6
        elif vol > 3.0: return 3
        else: return 2
    scored_df['Volatility_Score'] = scored_df['Volatility.D'].apply(volatility_score)
    scored_df['Investment_Score'] += scored_df['Volatility_Score'] * 0.10
    def mcap_score(mcap):
        if pd.isna(mcap): return 0
        if 1e9 <= mcap <= 50e9: return 10
        elif 50e9 < mcap <= 200e9: return 8
        elif 500e6 <= mcap < 1e9: return 6
        else: return 4
    scored_df['MCap_Score'] = scored_df['market_cap_basic'].apply(mcap_score)
    scored_df['Investment_Score'] += scored_df['MCap_Score'] * 0.10
    max_possible_score = 10 * (0.20 + 0.15 + 0.25 + 0.20 + 0.10 + 0.10)
    scored_df['Investment_Score'] = (scored_df['Investment_Score'] / max_possible_score) * 100
    scored_df['Investment_Score'] = scored_df['Investment_Score'].round(1)
    return scored_df

def get_tradingview_url(symbol):
    return f"https://www.tradingview.com/chart/?symbol={symbol}"

def fetch_screener_data():
    try:
        with st.spinner("🔍 Recupero dati dal mercato..."):
            query = (Query().set_markets('america', 'australia','belgium','brazil', 'canada', 'chile', 'china','italy','czech', 'denmark', 'egypt', 'estonia', 'finland', 'france', 'germany', 'greece','hongkong', 'hungary','india', 'indonesia', 'ireland', 'israel', 'japan','korea','kuwait', 'lithuania', 'luxembourg', 'malaysia', 'mexico', 'morocco', 'netherlands','newzealand', 'norway', 'peru', 'philippines', 'poland', 'portugal', 'qatar', 'russia','singapore', 'slovakia', 'spain', 'sweden', 'switzerland', 'taiwan', 'uae', 'uk','venezuela', 'vietnam', 'crypto')
                .select('name', 'description', 'country', 'sector', 'currency', 'close', 'change', 'volume','market_cap_basic', 'RSI', 'MACD.macd', 'MACD.signal', 'SMA50', 'SMA200','Volatility.D', 'Recommend.All', 'float_shares_percent_current','relative_volume_10d_calc', 'price_earnings_ttm', 'earnings_per_share_basic_ttm','Perf.W', 'Perf.1M')
                .where(Column('type').isin(['stock','etf']),Column('is_primary') == True,Column('market_cap_basic').between(10_000_000_000, 200_000_000_000_000),Column('close') > Column('SMA50'),Column('close') > Column('SMA100'),Column('close') > Column('SMA200'),Column('RSI').between(30, 80),Column('MACD.macd') > Column('MACD.signal'),Column('Volatility.D') > 0.2,Column('Recommend.All') > 0.1,Column('relative_volume_10d_calc') > 0.7,Column('float_shares_percent_current') > 0.3)
                .order_by('market_cap_basic', ascending=False)
                .limit(200))
            total, df = query.get_scanner_data()
            if not df.empty:
                df = calculate_investment_score(df)
                df['Rating'] = df['Recommend.All'].apply(format_technical_rating)
                df['Market Cap'] = df['market_cap_basic'].apply(lambda x: format_currency(x))
                df['Price'] = df['close'].round(2)
                df['Change %'] = df['change'].apply(format_percentage)
                df['Volume'] = df['volume'].apply(lambda x: format_currency(x, ''))
                df['RSI'] = df['RSI'].round(1)
                df['Volatility %'] = df['Volatility.D'].apply(format_percentage)
                df['TradingView_URL'] = df['name'].apply(get_tradingview_url)
                df['Perf Week %'] = df['Perf.W'].apply(format_percentage)
                df['Perf Month %'] = df['Perf.1M'].apply(format_percentage)
                df = df.rename(columns={'name': 'Symbol','description': 'Company','country': 'Country','sector': 'Sector','currency': 'Currency'})
                return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Errore nel recupero dati: {e}")
        return pd.DataFrame()

def get_top_5_investment_picks(df):
    if df.empty: return pd.DataFrame()
    top_5 = df.nlargest(5, 'Investment_Score').copy()
    def generate_recommendation_reason(row):
        reasons = []
        if row['RSI_Score'] >= 8: reasons.append("RSI ottimale")
        if row['MACD_Score'] >= 7: reasons.append("MACD positivo")
        if row['Trend_Score'] >= 8: reasons.append("Strong uptrend")
        if row['Tech_Rating_Score'] >= 8: reasons.append("Analisi tecnica positiva")
        if row['Volatility_Score'] >= 7: reasons.append("Volatilità controllata")
        return " | ".join(reasons[:3])
    top_5['Recommendation_Reason'] = top_5.apply(generate_recommendation_reason, axis=1)
    return top_5

# SEZIONE 3: TAB 3 - YFINANCE OTTIMIZZATO
def fetch_yfinance_data(ticker_symbol, period="1y"):
    try:
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period=period)
        info = stock.info
        company_name = info.get('longName', info.get('shortName', ticker_symbol))
        news = fetch_google_news_rss(ticker_symbol, company_name)
        return {'history': hist, 'info': info, 'news': news, 'ticker': stock, 'symbol': ticker_symbol, 'company_name': company_name}
    except Exception as e:
        st.error(f"❌ Errore nel caricamento dati: {e}")
        return None

def get_currency_symbol(ticker_data):
    info = ticker_data.get('info', {})
    currency_code = info.get('currency', 'USD')
    currency_map = {'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥','CHF': 'CHF', 'CAD': 'C$', 'AUD': 'A$', 'CNY': '¥','INR': '₹', 'BRL': 'R$', 'RUB': '₽', 'KRW': '₩','SEK': 'kr', 'NOK': 'kr', 'DKK': 'kr', 'PLN': 'zł','TRY': '₺', 'ZAR': 'R', 'MXN': '$', 'SGD': 'S$','HKD': 'HK$', 'NZD': 'NZ$', 'THB': '฿', 'PHP': '₱','MYR': 'RM', 'IDR': 'Rp', 'VND': '₫', 'TWD': 'NT$'}
    return currency_map.get(currency_code, currency_code)

def fetch_google_news_rss(ticker_symbol, company_name=None):
    try:
        if not company_name or company_name == ticker_symbol: query = f"{ticker_symbol} stock"
        else: query = f"{company_name} {ticker_symbol} stock"
        encoded_query = quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        news_list = []
        for entry in feed.entries[:10]:
            news_item = {'title': entry.get('title', 'N/A'),'link': entry.get('link', 'N/A'),'publisher': entry.get('source', {}).get('title', 'Google News'),'published': entry.get('published', 'N/A'),'summary': entry.get('summary', '')[:200]}
            news_list.append(news_item)
        return news_list
    except Exception as e:
        print(f"⚠️ Errore Google News RSS: {e}")
        return []

def calculate_volatility(close, period=20):
    try:
        returns = close.pct_change()
        volatility = returns.rolling(window=period).std() * np.sqrt(252)
        return volatility
    except: return None

def calculate_atr(high, low, close, period=14):
    try:
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr
    except: return None

def calculate_rsi(close, period=14):
    try:
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    except: return None

def calculate_macd(close):
    try:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd.iloc[-1]
    except: return 0

def calculate_dynamic_trading_signals(data, atr_multiplier_sl=2.0, atr_multiplier_tp=3.5):
    try:
        close = data['Close']
        high = data['High']
        low = data['Low']
        volume = data['Volume']
        rsi = calculate_rsi(close)
        macd = calculate_macd(close)
        atr = calculate_atr(high, low, close, 14)
        volatility = calculate_volatility(close, 20)
        sma50 = close.rolling(window=50).mean()
        
        current_price = close.iloc[-1]
        latest_rsi = rsi.iloc[-1] if rsi is not None else 50
        latest_atr = atr.iloc[-1] if atr is not None else current_price * 0.02
        latest_vol = volatility.iloc[-1] if volatility is not None else 0.3
        latest_sma50 = sma50.iloc[-1]
        
        bb_upper = latest_sma50 + (latest_sma50 * 0.05)
        bb_lower = latest_sma50 - (latest_sma50 * 0.05)
        avg_vol = volume.rolling(20).mean().iloc[-1]
        vol_ratio = volume.iloc[-1] / avg_vol if avg_vol > 0 else 1.0
        
        signal = {'direction': 'HOLD','confidence': 0.0,'entry_point': current_price,'stop_loss': current_price,'take_profit': current_price,'risk_reward_ratio': 0.0,'atr': latest_atr,'atr_percent': (latest_atr/current_price)*100,'volatility': latest_vol*100,'rsi': latest_rsi,'support': bb_lower,'resistance': bb_upper,'volume_ratio': vol_ratio}
        
        buy_signal = latest_rsi < 35 or (current_price < bb_lower and macd > 0)
        sell_signal = latest_rsi > 75 or (current_price > bb_upper and macd < 0)
        
        if buy_signal:
            signal['direction'] = 'BUY'
            signal['confidence'] = 0.75
            signal['entry_point'] = max(bb_lower, current_price * 0.99)
            signal['stop_loss'] = signal['entry_point'] - latest_atr * atr_multiplier_sl
            signal['take_profit'] = signal['entry_point'] + latest_atr * atr_multiplier_tp
        elif sell_signal:
            signal['direction'] = 'SELL'
            signal['confidence'] = 0.75
            signal['entry_point'] = min(bb_upper, current_price * 1.01)
            signal['stop_loss'] = signal['entry_point'] + latest_atr * atr_multiplier_sl
            signal['take_profit'] = signal['entry_point'] - latest_atr * atr_multiplier_tp
        else:
            signal['confidence'] = 0.5
        
        risk = abs(signal['entry_point'] - signal['stop_loss'])
        reward = abs(signal['take_profit'] - signal['entry_point'])
        signal['risk_reward_ratio'] = reward / risk if risk > 0 else 0.0
        signal['sl_distance_percent'] = (risk / signal['entry_point']) * 100
        signal['tp_distance_percent'] = (reward / signal['entry_point']) * 100
        return signal
    except Exception as e:
        st.error(f"Errore nel calcolo dei segnali: {e}")
        return None

def calculate_dcf_valuation(ticker_data):
    try:
        info = ticker_data['info']
        fcf = info.get('freeCashflow', 0)
        if not fcf or fcf == 0: return None
        
        beta = info.get('beta', 1.0) or 1.0
        cost_of_equity = 0.045 + beta * 0.065
        wacc = max(cost_of_equity * 0.8, 0.07)
        growth_rate = 0.05
        projected_fcf = [fcf * ((1 + growth_rate) ** y) for y in range(1, 6)]
        terminal_fcf = projected_fcf[-1] * 1.025
        terminal_value = terminal_fcf / (wacc - 0.025) if wacc > 0.025 else terminal_fcf / 0.05
        pv_fcf = sum(f / ((1 + wacc) ** (i+1)) for i, f in enumerate(projected_fcf))
        pv_terminal = terminal_value / ((1 + wacc) ** 5)
        ev = pv_fcf + pv_terminal
        shares = info.get('sharesOutstanding', 1)
        intrinsic = ev / shares
        current_price = info.get('currentPrice', 1)
        upside = ((intrinsic / current_price) - 1) * 100
        
        return {'intrinsic_value': intrinsic,'current_price': current_price,'upside_downside': upside,'wacc': wacc,'recommendation': 'STRONG BUY' if upside > 30 else 'BUY' if upside > 15 else 'HOLD' if upside > -15 else 'SELL'}
    except: return None

# SEZIONE 4: AGENTI AI (max 400 parole)
def generate_technical_agent_analysis(signal: dict, ticker_symbol: str) -> str:
    prompt = f"Analista Tecnico di {ticker_symbol}: Segnale {signal['direction']} ({signal['confidence']*100:.0f}%), RSI {signal['rsi']:.1f}, ATR {signal['atr']:.2f} ({signal['atr_percent']:.1f}%), Volatilità {signal['volatility']:.1f}%, Risk/Reward 1:{signal['risk_reward_ratio']:.2f}. Analisi BREVE (max 400 parole): 1) Interpretazione segnale, 2) Qualità volatilità, 3) Risk/Reward, 4) Raccomandazione, 5) RATING: Strong Buy/Buy/Hold/Sell."
    try:
        response = call_groq_api(prompt, max_tokens=400)
        return response
    except Exception as e:
        return f"❌ Errore: {str(e)}"

def generate_fundamental_agent_analysis(ticker_data: dict, ticker_symbol: str) -> str:
    info = ticker_data['info']
    dcf = calculate_dcf_valuation(ticker_data)
    dcf_text = f"DCF: ${dcf['intrinsic_value']:.2f} vs ${dcf['current_price']:.2f} ({dcf['upside_downside']:.1f}%), {dcf['recommendation']}" if dcf else "DCF non disponibile"
    prompt = f"Analista Fondamentale {ticker_symbol}: P/E {info.get('trailingPE', 'N/A')}, ROE {info.get('returnOnEquity', 'N/A')}, Rev Growth {info.get('revenueGrowth', 'N/A')}, Debt/Eq {info.get('debtToEquity', 'N/A')}. {dcf_text}. Analisi BREVE (max 400 parole): 1) Valutazione, 2) DCF vs Multipli, 3) Qualità FCF, 4) Solidità, 5) RATING: Strong Buy/Buy/Hold/Sell."
    try:
        response = call_groq_api(prompt, max_tokens=400)
        return response
    except Exception as e:
        return f"❌ Errore: {str(e)}"

def generate_news_sentiment_agent_analysis(ticker_data: dict, ticker_symbol: str) -> str:
    news_text = "\n".join([f"{i}. {n.get('title', 'N/A')}" for i, n in enumerate(ticker_data.get('news', [])[:5], 1)])
    prompt = f"Analista Sentiment {ticker_symbol}. Notizie: {news_text or 'Nessuna'}. Analisi BREVE (max 400 parole): 1) Sentiment (Pos/Neu/Neg), 2) Impatto, 3) Rischi, 4) Catalizzatori, 5) RATING: Strong Buy/Buy/Hold/Sell."
    try:
        response = call_groq_api(prompt, max_tokens=400)
        return response
    except Exception as e:
        return f"❌ Errore: {str(e)}"

def generate_consensus_analysis(tech: str, fund: str, sentiment: str, ticker_symbol: str) -> str:
    prompt = f"Moderatore Team {ticker_symbol}. Tech: {tech[:100]}... Fund: {fund[:100]}... News: {sentiment[:100]}... Analisi BREVE (max 400 parole): 1) Consenso, 2) Accordi/Disaccordi, 3) Fattore critico, 4) Coerenza, 5) RACCOMANDAZIONE FINALE, 6) Confidence, 7) Rischi."
    try:
        response = call_groq_api(prompt, max_tokens=400)
        return response
    except Exception as e:
        return f"❌ Errore: {str(e)}"

def display_multi_agent_analysis(ticker_data: dict, signal: dict, ticker_symbol: str):
    st.markdown("---")
    st.subheader("🤖 ANALISI MULTI-AGENTE AI")
    col_info = st.container()
    col_info.info("⏳ Generazione analisi AI...")
    
    placeholder_tech = st.empty()
    placeholder_fund = st.empty()
    placeholder_sentiment = st.empty()
    
    placeholder_tech.info("🔧 Agente Tecnico...")
    tech = generate_technical_agent_analysis(signal, ticker_symbol)
    placeholder_tech.empty()
    
    placeholder_fund.info("📊 Agente Fondamentale...")
    fund = generate_fundamental_agent_analysis(ticker_data, ticker_symbol)
    placeholder_fund.empty()
    
    placeholder_sentiment.info("📰 Agente Sentiment...")
    sentiment = generate_news_sentiment_agent_analysis(ticker_data, ticker_symbol)
    placeholder_sentiment.empty()
    
    tab_tech, tab_fund, tab_news, tab_consensus = st.tabs(["🔧 Tecnico", "📊 Fondamentale", "📰 Sentiment", "🎯 Consenso"])
    
    with tab_tech:
        st.markdown(tech)
    with tab_fund:
        st.markdown(fund)
    with tab_news:
        st.markdown(sentiment)
    with tab_consensus:
        st.info("⏳ Generazione consenso...")
        consensus = generate_consensus_analysis(tech, fund, sentiment, ticker_symbol)
        st.markdown(consensus)
        
        report = f"REPORT {ticker_symbol} - {datetime.now().strftime('%d/%m/%Y')}\n\nTECNICO:\n{tech}\n\nFONDAMENTALE:\n{fund}\n\nSENTIMENT:\n{sentiment}\n\nCONSENSO:\n{consensus}"
        st.download_button(label="📥 Scarica Report", data=report, file_name=f"Report_{ticker_symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", mime="text/plain", use_container_width=True)

# SEZIONE 5: MAIN - TAB 1 e 2 INTATTE
def stock_screener_app():
    if 'data' not in st.session_state: st.session_state.data = pd.DataFrame()
    if 'last_update' not in st.session_state: st.session_state.last_update = None
    if 'top_5_stocks' not in st.session_state: st.session_state.top_5_stocks = pd.DataFrame()
    
    st.title("📈 Financial Screener Dashboard")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("🔄 Aggiorna Dati", type="primary", use_container_width=True):
            new_data = fetch_screener_data()
            if not new_data.empty:
                st.session_state.data = new_data
                st.session_state.top_5_stocks = get_top_5_investment_picks(new_data)
                st.session_state.last_update = datetime.now()
                st.success(f"✅ Aggiornati {len(new_data)} titoli")
    
    if st.session_state.last_update:
        st.info(f"🕐 Ultimo aggiornamento: {st.session_state.last_update.strftime('%d/%m/%Y %H:%M:%S')}")
    
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "🎯 Top Picks", "🔍 Analisi Avanzata"])
    
    # ===== TAB 1: DASHBOARD (INVARIATO) =====
    with tab1:
        if not st.session_state.data.empty:
            df = st.session_state.data
            
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1: st.metric("Titoli", len(df))
            with col2: st.metric("Buy", len(df[df['Rating'].str.contains('Buy', na=False)]))
            with col3: st.metric("Strong Buy", len(df[df['Rating'].str.contains('Strong Buy', na=False)]))
            with col4: st.metric("Rating Medio", f"{df['Recommend.All'].mean():.2f}")
            with col5: st.metric("Score Medio", f"{df['Investment_Score'].mean():.1f}")
            
            st.subheader("🔍 Filtri")
            col1, col2, col3, col4 = st.columns(4)
            with col1: selected_country = st.selectbox("Paese", ['Tutti'] + sorted(df['Country'].unique().tolist()))
            with col2: selected_sector = st.selectbox("Settore", ['Tutti'] + sorted(df['Sector'].dropna().unique().tolist()))
            with col3: selected_rating = st.selectbox("Rating", ['Tutti'] + sorted(df['Rating'].unique().tolist()))
            with col4: min_score = st.slider("Score Minimo", 0, 100, 50)
            
            filtered_df = df.copy()
            if selected_country != 'Tutti': filtered_df = filtered_df[filtered_df['Country'] == selected_country]
            if selected_sector != 'Tutti': filtered_df = filtered_df[filtered_df['Sector'] == selected_sector]
            if selected_rating != 'Tutti': filtered_df = filtered_df[filtered_df['Rating'] == selected_rating]
            filtered_df = filtered_df[filtered_df['Investment_Score'] >= min_score]
            
            st.subheader("📋 Dati Dettagliati")
            st.markdown(f"**Visualizzati {len(filtered_df)} di {len(df)} titoli**")
            
            display_columns = st.multiselect("Colonne:", ['Company', 'Symbol', 'Country', 'Sector', 'Price', 'Rating', 'Investment_Score', 'TradingView_URL'], default=['Company', 'Symbol', 'Investment_Score', 'Price', 'Rating'])
            
            if display_columns:
                display_df = filtered_df[display_columns].copy()
                st.dataframe(display_df, use_container_width=True, height=400)
                
                csv = display_df.to_csv(index=False)
                st.download_button(label="📥 Scarica CSV", data=csv, file_name=f"screener_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv", use_container_width=True)
        else:
            st.markdown("## 🚀 Clicca 'Aggiorna Dati' per iniziare!")
    
    # ===== TAB 2: TOP PICKS (INVARIATO) =====
    with tab2:
        if not st.session_state.top_5_stocks.empty:
            st.subheader("🎯 TOP 5 PICKS")
            for idx, (_, stock) in enumerate(st.session_state.top_5_stocks.iterrows(), 1):
                st.markdown(f"**#{idx} {stock['Company']} ({stock['Symbol']})** - Score {stock['Investment_Score']:.1f}")
                st.markdown(f"💰 ${stock['Price']} | {stock['Country']} | {stock['Sector']} | {stock['Rating']}")
                st.caption(stock['Recommendation_Reason'])
                st.markdown("---")
        else:
            st.info("Aggiorna dati per vedere i top picks")
    
    # ===== TAB 3: ANALISI AVANZATA (NUOVO) =====
    with tab3:
        st.subheader("🔍 Analisi Multi-Agente Avanzata")
        ticker_input = st.text_input("Inserisci ticker:", placeholder="AAPL")
        if st.button("🔎 Analizza"):
            if ticker_input:
                with st.spinner("Analisi in corso..."):
                    ticker_data = fetch_yfinance_data(ticker_input.upper())
                    if ticker_data and ticker_data['info']:
                        symbol = get_currency_symbol(ticker_data)
                        current_price = ticker_data['history']['Close'].iloc[-1]
                        info = ticker_data['info']
                        
                        st.markdown("---")
                        col1, col2, col3, col4, col5 = st.columns(5)
                        with col1: st.metric("Prezzo", f"{symbol}{current_price:.2f}")
                        with col2: st.metric("Market Cap", f"{symbol}{info.get('marketCap', 0)/1e9:.2f}B")
                        with col3: st.metric("P/E", f"{info.get('trailingPE', 'N/A')}")
                        with col4: st.metric("Beta", f"{info.get('beta', 'N/A')}")
                        with col5: st.metric("Div Yield", f"{info.get('dividendYield', 0)*100:.2f}%")
                        
                        signal = calculate_dynamic_trading_signals(ticker_data['history'])
                        if signal:
                            col1, col2, col3, col4 = st.columns(4)
                            with col1: st.metric("Segnale", signal['direction'])
                            with col2: st.metric("ATR", f"{symbol}{signal['atr']:.2f}")
                            with col3: st.metric("Volatilità", f"{signal['volatility']:.1f}%")
                            with col4: st.metric("Risk/Reward", f"1:{signal['risk_reward_ratio']:.2f}")
                            
                            st.markdown("### 📍 Livelli")
                            col1, col2, col3 = st.columns(3)
                            with col1: st.markdown(f"**Entry:** `{symbol}{signal['entry_point']:.2f}`")
                            with col2: st.markdown(f"**SL:** `{symbol}{signal['stop_loss']:.2f}`")
                            with col3: st.markdown(f"**TP:** `{symbol}{signal['take_profit']:.2f}`")
                        
                        if ticker_data.get('news'):
                            st.markdown("---")
                            st.subheader("📰 Notizie")
                            for i, n in enumerate(ticker_data['news'][:3], 1):
                                with st.expander(f"📰 {n.get('title', 'N/A')[:60]}..."):
                                    st.write(f"**Publisher:** {n.get('publisher')}")
                                    st.link_button("Leggi", n.get('link'))
                        
                        if signal:
                            display_multi_agent_analysis(ticker_data, signal, ticker_input.upper())
                    else: st.error(f"Dati non trovati per {ticker_input.upper()}")

if __name__ == "__main__":
    stock_screener_app()
