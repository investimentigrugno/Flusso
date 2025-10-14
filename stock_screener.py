# stock_screener.py
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
from deep_translator import GoogleTranslator, single_detection
from typing import List, Dict
import re

# --- API CONFIGURATION ---
FINNHUB_API_KEY = "d38fnb9r01qlbdj59nogd38fnb9r01qlbdj59np0"
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

# --- FUNZIONI PER LA TRADUZIONE ---
def detect_language_deep(text):
    """Rileva la lingua del testo usando deep-translator"""
    if not text:
        return "en"
    try:
        if any(ord(char) > 127 for char in text):
            return "auto"
        english_keywords = ['stock', 'market', 'price', 'shares', 'trading', 'financial',
                          'earnings', 'revenue', 'profit', 'loss', 'company', 'business',
                          'the', 'and', 'of', 'to', 'in', 'for', 'with', 'on', 'at']
        text_lower = text.lower()
        english_word_count = sum(1 for word in english_keywords if word in text_lower)
        if english_word_count >= 3:
            return "en"
        else:
            return "auto"
    except Exception:
        return "en"

def translate_text_deep(text, source_lang, target_lang):
    """Traduce il testo usando deep-translator"""
    if not text:
        return text
    try:
        translator = GoogleTranslator(source=source_lang, target=target_lang)
        translated = translator.translate(text)
        return translated if translated else text
    except Exception as e:
        print(f"Errore traduzione: {e}")
        return text

def test_deep_translate():
    """Testa la connessione a deep-translator"""
    try:
        translator = GoogleTranslator(source='en', target='it')
        test_result = translator.translate("Hello World")
        return test_result and test_result != "Hello World"
    except Exception:
        return False

def fetch_finnhub_market_news(count=8):
    """Recupera notizie reali da Finnhub API e le traduce in italiano"""
    try:
        url = f"{FINNHUB_BASE_URL}/news"
        params = {
            'category': 'general',
            'token': FINNHUB_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            st.error(f"Errore API Finnhub: {response.status_code}")
            return []
        
        news_data = response.json()
        formatted_news = []
        
        for news in news_data[:count]:
            title = news.get('headline', 'Titolo non disponibile')
            description = news.get('summary', 'Descrizione non disponibile')
            
            title_lang = detect_language_deep(title)
            desc_lang = detect_language_deep(description)
            
            translated_title = title
            translated_description = description
            
            if title_lang == "en":
                translated_title = translate_text_deep(title, "en", "it")
            if desc_lang == "en":
                translated_description = translate_text_deep(description, "en", "it")
            
            formatted_news.append({
                'title': translated_title,
                'description': translated_description,
                'impact': '📊 Impatto sui mercati',
                'date': datetime.fromtimestamp(news.get('datetime', 0)).strftime('%d %b %Y'),
                'source': news.get('source', 'Finnhub'),
                'url': news.get('url', ''),
                'category': 'general',
                'translated': title_lang == "en" or desc_lang == "en"
            })
        
        return formatted_news
    except Exception as e:
        st.error(f"Errore Finnhub: {e}")
        return []

def fetch_company_news_finnhub(symbol, days_back=7, limit=3):
    """Recupera notizie specifiche per company da Finnhub e le traduce"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        url = f"{FINNHUB_BASE_URL}/company-news"
        params = {
            'symbol': symbol,
            'from': start_date.strftime('%Y-%m-%d'),
            'to': end_date.strftime('%Y-%m-%d'),
            'token': FINNHUB_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            return []
        
        news_data = response.json()
        formatted_news = []
        
        for news in news_data[:limit]:
            title = news.get('headline', 'Titolo non disponibile')
            description = news.get('summary', 'Descrizione non disponibile')
            
            title_lang = detect_language_deep(title)
            desc_lang = detect_language_deep(description)
            
            translated_title = title
            translated_description = description
            
            if title_lang == "en":
                translated_title = translate_text_deep(title, "en", "it")
            if desc_lang == "en":
                translated_description = translate_text_deep(description, "en", "it")
            
            formatted_news.append({
                'title': translated_title,
                'description': translated_description,
                'impact': f'📊 Impatto su {symbol}',
                'date': datetime.fromtimestamp(news.get('datetime', 0)).strftime('%d %b %Y'),
                'source': news.get('source', 'Finnhub'),
                'url': news.get('url', ''),
                'category': 'company_specific',
                'symbol': symbol,
                'translated': title_lang == "en" or desc_lang == "en"
            })
        
        return formatted_news
    except Exception as e:
        return []

def fetch_mixed_finnhub_news(count=8):
    """Recupera un mix di notizie generali e company-specific tradotte"""
    try:
        with st.spinner("🌐 Recupero e traduco notizie con Deep-Translator..."):
            general_news = fetch_finnhub_market_news(count//2)
            
            company_news = []
            if not st.session_state.top_5_stocks.empty:
                top_symbols = st.session_state.top_5_stocks['Symbol'].head(2).tolist()
                for symbol in top_symbols:
                    company_specific = fetch_company_news_finnhub(symbol, limit=1)
                    company_news.extend(company_specific)
            
            all_news = general_news + company_news
            return all_news[:count]
    except Exception as e:
        st.error(f"Errore nel recupero notizie: {e}")
        return []

def test_finnhub_connection():
    """Testa la connessione all'API Finnhub"""
    try:
        url = f"{FINNHUB_BASE_URL}/quote"
        params = {
            'symbol': 'AAPL',
            'token': FINNHUB_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('c') is not None
        return False
    except:
        return False

def format_technical_rating(rating: float) -> str:
    """Format technical rating"""
    if pd.isna(rating):
        return 'N/A'
    elif rating >= 0.5:
        return '🟢 Strong Buy'
    elif rating >= 0.1:
        return '🟢 Buy'
    elif rating >= -0.1:
        return '🟡 Neutral'
    elif rating >= -0.5:
        return '🔴 Sell'
    else:
        return '🔴 Strong Sell'

def format_currency(value, currency='$'):
    """Format currency values"""
    if pd.isna(value):
        return "N/A"
    if value >= 1e12:
        return f"{currency}{value/1e12:.2f}T"
    elif value >= 1e9:
        return f"{currency}{value/1e9:.2f}B"
    elif value >= 1e6:
        return f"{currency}{value/1e6:.2f}M"
    else:
        return f"{currency}{value:.2f}"

def format_percentage(value):
    """Format percentage values"""
    if pd.isna(value):
        return "N/A"
    return f"{value:.2f}%"

def calculate_investment_score(df):
    """Calcola un punteggio di investimento per ogni azione"""
    scored_df = df.copy()
    scored_df['Investment_Score'] = 0.0
    
    # 1. RSI Score (peso 20%)
    def rsi_score(rsi):
        if pd.isna(rsi):
            return 0
        if 50 <= rsi <= 70:
            return 10
        elif 40 <= rsi < 50:
            return 7
        elif 30 <= rsi < 40:
            return 5
        elif rsi > 80:
            return 2
        else:
            return 1
    
    scored_df['RSI_Score'] = scored_df['RSI'].apply(rsi_score)
    scored_df['Investment_Score'] += scored_df['RSI_Score'] * 0.20
    
    # 2. MACD Score (peso 15%)
    def macd_score(macd, signal):
        if pd.isna(macd) or pd.isna(signal):
            return 0
        diff = macd - signal
        if diff > 0.05:
            return 10
        elif diff > 0:
            return 7
        elif diff > -0.05:
            return 4
        else:
            return 1
    
    scored_df['MACD_Score'] = scored_df.apply(
        lambda row: macd_score(
            row.get('MACD.macd', None) if 'MACD.macd' in row.index else row.get('macd', None),
            row.get('MACD.signal', None) if 'MACD.signal' in row.index else row.get('signal', None)
        ), axis=1
    )
    scored_df['Investment_Score'] += scored_df['MACD_Score'] * 0.15
    
    # 3. Trend Score (peso 25%)
    def trend_score(price, sma50, sma200):
        if pd.isna(price) or pd.isna(sma50) or pd.isna(sma200):
            return 0
        score = 0
        if price > sma50:
            score += 5
        if price > sma200:
            score += 3
        if sma50 > sma200:
            score += 2
        return score
    
    scored_df['Trend_Score'] = scored_df.apply(
        lambda row: trend_score(row['close'], row['SMA50'], row['SMA200']), axis=1
    )
    scored_df['Investment_Score'] += scored_df['Trend_Score'] * 0.25
    
    # 4. Technical Rating Score (peso 20%)
    def tech_rating_score(rating):
        if pd.isna(rating):
            return 0
        if rating >= 0.5:
            return 10
        elif rating >= 0.3:
            return 8
        elif rating >= 0.1:
            return 6
        elif rating >= -0.1:
            return 4
        else:
            return 2
    
    scored_df['Tech_Rating_Score'] = scored_df['Recommend.All'].apply(tech_rating_score)
    scored_df['Investment_Score'] += scored_df['Tech_Rating_Score'] * 0.20
    
    # 5. Volatility Score (peso 10%)
    def volatility_score(vol):
        if pd.isna(vol):
            return 0
        if 0.5 <= vol <= 2.0:
            return 10
        elif 0.3 <= vol < 0.5:
            return 7
        elif 2.0 < vol <= 3.0:
            return 6
        elif vol > 3.0:
            return 3
        else:
            return 2
    
    scored_df['Volatility_Score'] = scored_df['Volatility.D'].apply(volatility_score)
    scored_df['Investment_Score'] += scored_df['Volatility_Score'] * 0.10
    
    # 6. Market Cap Score (peso 10%)
    def mcap_score(mcap):
        if pd.isna(mcap):
            return 0
        if 1e9 <= mcap <= 50e9:
            return 10
        elif 50e9 < mcap <= 200e9:
            return 8
        elif 500e6 <= mcap < 1e9:
            return 6
        else:
            return 4
    
    scored_df['MCap_Score'] = scored_df['market_cap_basic'].apply(mcap_score)
    scored_df['Investment_Score'] += scored_df['MCap_Score'] * 0.10
    
    # Normalizza il punteggio finale (0-100)
    max_possible_score = 10 * (0.20 + 0.15 + 0.25 + 0.20 + 0.10 + 0.10)
    scored_df['Investment_Score'] = (scored_df['Investment_Score'] / max_possible_score) * 100
    scored_df['Investment_Score'] = scored_df['Investment_Score'].round(1)
    
    return scored_df

def get_tradingview_url(symbol):
    """Generate TradingView URL for a given symbol"""
    if ':' in symbol:
        clean_symbol = symbol.split(':')[1]
    else:
        clean_symbol = symbol
    return f"https://www.tradingview.com/chart/?symbol={symbol}"

def fetch_screener_data():
    """Fetch data from TradingView screener"""
    try:
        with st.spinner("🔍 Recupero dati dal mercato..."):
            query = (
                Query()
                .select('name', 'description', 'country', 'sector', 'currency', 'close', 'change', 'volume',
                       'market_cap_basic', 'RSI', 'MACD.macd', 'MACD.signal', 'SMA50', 'SMA200',
                       'Volatility.D', 'Recommend.All', 'float_shares_percent_current',
                       'relative_volume_10d_calc', 'price_earnings_ttm', 'earnings_per_share_basic_ttm',
                       'Perf.W', 'Perf.1M')
                .where(
                    Column('type').isin(['stock']),
                    Column('market_cap_basic').between(1_000_000_000, 200_000_000_000_000),
                    Column('close') > Column('SMA50'),
                    Column('close') > Column('SMA200'),
                    Column('RSI').between(30, 80),
                    Column('MACD.macd') > Column('MACD.signal'),
                    Column('Volatility.D') > 0.2,
                    Column('Recommend.All') > 0.1,
                    Column('float_shares_percent_current') > 0.3,
                )
                .order_by('market_cap_basic', ascending=False)
                .limit(300)
                .get_scanner_data()
            )
            
            df = query[1]
            
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
                
                df = df.rename(columns={
                    'name': 'Symbol',
                    'description': 'Company',
                    'country': 'Country',
                    'sector': 'Sector',
                    'currency': 'Currency'
                })
            
            return df
    except Exception as e:
        st.error(f"❌ Errore nel recupero dati: {e}")
        return pd.DataFrame()

def get_top_5_investment_picks(df):
    """Seleziona le top 5 azioni"""
    if df.empty:
        return pd.DataFrame()
    
    top_5 = df.nlargest(5, 'Investment_Score').copy()
    
    def generate_recommendation_reason(row):
        reasons = []
        if row['RSI_Score'] >= 8:
            reasons.append("RSI ottimale")
        if row['MACD_Score'] >= 7:
            reasons.append("MACD positivo")
        if row['Trend_Score'] >= 8:
            reasons.append("Strong uptrend")
        if row['Tech_Rating_Score'] >= 8:
            reasons.append("Analisi tecnica positiva")
        if row['Volatility_Score'] >= 7:
            reasons.append("Volatilità controllata")
        return " | ".join(reasons[:3])
    
    top_5['Recommendation_Reason'] = top_5.apply(generate_recommendation_reason, axis=1)
    
    return top_5

# ===============================
# FUNZIONE PRINCIPALE DELL'APP
# ===============================
def stock_screener_app():
    """Funzione principale per l'app dello stock screener"""
    
    # Session state initialization
    if 'data' not in st.session_state:
        st.session_state.data = pd.DataFrame()
    if 'last_update' not in st.session_state:
        st.session_state.last_update = None
    if 'top_5_stocks' not in st.session_state:
        st.session_state.top_5_stocks = pd.DataFrame()
    if 'market_news' not in st.session_state:
        st.session_state.market_news = []
    
    # Main UI
    st.title("📈 Financial Screener Dashboard")
    st.markdown("Analizza le migliori opportunità di investimento con criteri tecnici avanzati e **notizie tradotte automaticamente** in italiano")
    
    # Status system
    with st.expander("🔑 Stato Sistema", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🌐 API Finnhub**")
            if test_finnhub_connection():
                st.success("✅ Connessione attiva")
            else:
                st.warning("⚠️ API non disponibile")
        
        with col2:
            st.markdown("**🌐 Google Translate**")
            if test_deep_translate():
                st.success("✅ Traduzione attiva")
            else:
                st.warning("⚠️ Traduzione non disponibile")
    
    st.markdown("---")
    
    # Main controls
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        if st.button("🔄 Aggiorna Dati", type="primary", use_container_width=True):
            new_data = fetch_screener_data()
            if not new_data.empty:
                st.session_state.data = new_data
                st.session_state.top_5_stocks = get_top_5_investment_picks(new_data)
                st.session_state.market_news = fetch_mixed_finnhub_news(8)
                st.session_state.last_update = datetime.now()
                st.success(f"✅ Aggiornati {len(new_data)} titoli")
            else:
                st.warning("⚠️ Nessun dato trovato")
    
    with col2:
        if st.button("🧹 Pulisci Cache", use_container_width=True):
            st.success("✅ Cache pulita!")
    
    with col3:
        auto_refresh = st.checkbox("🔄 Auto-refresh (30s)")
        if auto_refresh:
            time.sleep(30)
            st.rerun()
    
    if st.session_state.last_update:
        st.info(f"🕐 Ultimo aggiornamento: {st.session_state.last_update.strftime('%d/%m/%Y %H:%M:%S')}")
    
    # TAB SYSTEM
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "🎯 Top Picks", "📰 Notizie", "🔍 TradingView Search"])
    
    with tab1:
        if not st.session_state.data.empty:
            df = st.session_state.data
            
            st.subheader("📊 Riepilogo")
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("Totale Titoli", len(df))
            with col2:
                buy_signals = len(df[df['Rating'].str.contains('Buy', na=False)])
                st.metric("Segnali Buy", buy_signals)
            with col3:
                strong_buy = len(df[df['Rating'].str.contains('Strong Buy', na=False)])
                st.metric("Strong Buy", strong_buy)
            with col4:
                avg_rating = df['Recommend.All'].mean()
                st.metric("Rating Medio", f"{avg_rating:.2f}")
            with col5:
                avg_score = df['Investment_Score'].mean()
                st.metric("Score Medio", f"{avg_score:.1f}/100")
            
            st.subheader("🔍 Filtri")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                countries = ['Tutti'] + sorted(df['Country'].unique().tolist())
                selected_country = st.selectbox("Paese", countries)
            with col2:
                sectors = ['Tutti'] + sorted(df['Sector'].dropna().unique().tolist())
                selected_sector = st.selectbox("Settore", sectors)
            with col3:
                ratings = ['Tutti'] + sorted(df['Rating'].unique().tolist())
                selected_rating = st.selectbox("Rating", ratings)
            with col4:
                min_score = st.slider("Score Minimo", 0, 100, 50)
            
            filtered_df = df.copy()
            if selected_country != 'Tutti':
                filtered_df = filtered_df[filtered_df['Country'] == selected_country]
            if selected_sector != 'Tutti':
                filtered_df = filtered_df[filtered_df['Sector'] == selected_sector]
            if selected_rating != 'Tutti':
                filtered_df = filtered_df[filtered_df['Rating'] == selected_rating]
            filtered_df = filtered_df[filtered_df['Investment_Score'] >= min_score]
            
            st.subheader("📋 Dati Dettagliati")
            st.markdown(f"**Visualizzati {len(filtered_df)} di {len(df)} titoli**")
            
            available_columns = ['Company', 'Symbol', 'Country', 'Sector', 'Price', 'Rating', 'Investment_Score']
            display_columns = st.multiselect(
                "Seleziona colonne:",
                available_columns,
                default=['Company', 'Symbol', 'Investment_Score', 'Price']
            )
            
            if display_columns:
                display_df = filtered_df[display_columns].copy()
                st.dataframe(display_df, use_container_width=True, height=400)
        else:
            st.info("👆 Clicca su 'Aggiorna Dati' per iniziare l'analisi!")
    
    with tab2:
        if not st.session_state.top_5_stocks.empty:
            st.subheader("🎯 TOP 5 PICKS")
            top_5 = st.session_state.top_5_stocks
            
            for idx, (_, stock) in enumerate(top_5.iterrows(), 1):
                with st.container():
                    col1, col2, col3 = st.columns([1, 3, 1])
                    
                    with col1:
                        st.markdown(f"### #{idx}")
                        st.markdown(f"**Score: {stock['Investment_Score']:.1f}/100**")
                    
                    with col2:
                        st.markdown(f"**{stock['Company']}** ({stock['Symbol']})")
                        st.markdown(f"*{stock['Country']} | {stock['Sector']}*")
                        st.markdown(f"💰 **${stock['Price']}**")
                    
                    with col3:
                        tv_url = stock['TradingView_URL']
                        st.link_button(f"📈 Chart", tv_url, use_container_width=True)
                    
                    st.markdown("---")
        else:
            st.info("📊 Aggiorna i dati per TOP 5 picks!")
    
    with tab3:
        if st.session_state.market_news:
            st.subheader("📰 Notizie di Mercato")
            
            for news in st.session_state.market_news:
                with st.container():
                    st.markdown(f"**{news['title']}**")
                    st.markdown(f"*{news['date']} - {news['source']}*")
                    st.markdown(news['description'])
                    if news.get('url'):
                        st.markdown(f"[Leggi articolo]({news['url']})")
                    st.markdown("---")
        else:
            st.info("📰 Aggiorna i dati per le notizie!")
    
    with tab4:
        st.header("🔍 Ricerca TradingView")
        symbol = st.text_input("Inserisci simbolo:", "")
        
        if symbol:
            url = f"https://www.tradingview.com/chart/?symbol={symbol.upper()}"
            st.markdown(f"[Apri grafico per {symbol}]({url})")
    
    # Sidebar info
    st.sidebar.title("ℹ️ Informazioni")
    st.sidebar.markdown("""
    ### 🎯 Funzionalità:
    
    - **🏆 TOP 5 PICKS**: Algoritmo AI
    - **🧮 Investment Score**: 6 fattori
    - **📈 TradingView**: Integrazione diretta
    - **📰 Notizie**: Tradotte con Google Translate
    """)
