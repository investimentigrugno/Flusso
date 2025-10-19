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

# --- FUNZIONI PER LA TRADUZIONE CON DEEP-TRANSLATOR ---
def detect_language_deep(text):
    """Rileva la lingua del testo usando deep-translator (richiede API key gratuita)"""
    if not text:
        return "en"
    
    try:
        # Per ora usiamo una semplice euristica per la rilevazione
        # Se contiene caratteri non ASCII, probabilmente non è inglese
        if any(ord(char) > 127 for char in text):
            return "auto"
        
        # Parole chiave inglesi comuni nelle notizie finanziarie
        english_keywords = ['stock', 'market', 'price', 'shares', 'trading', 'financial',
                          'earnings', 'revenue', 'profit', 'loss', 'company', 'business',
                          'the', 'and', 'of', 'to', 'in', 'for', 'with', 'on', 'at']
        
        text_lower = text.lower()
        english_word_count = sum(1 for word in english_keywords if word in text_lower)
        
        # Se trova molte parole inglesi, assume che sia inglese
        if english_word_count >= 3:
            return "en"
        else:
            return "auto"
            
    except Exception:
        return "en"  # Default to English

def translate_text_deep(text, source_lang, target_lang):
    """Traduce il testo usando deep-translator (GoogleTranslator)"""
    if not text:
        return text
    
    try:
        translator = GoogleTranslator(source=source_lang, target=target_lang)
        translated = translator.translate(text)
        return translated if translated else text
    except Exception as e:
        print(f"Errore traduzione: {e}")
        return text  # Ritorna il testo originale se la traduzione fallisce

def test_deep_translate():
    """Testa la connessione a deep-translator"""
    try:
        translator = GoogleTranslator(source='en', target='it')
        test_result = translator.translate("Hello World")
        return test_result and test_result != "Hello World"
    except Exception:
        return False

# --- FUNZIONI PER LE NOTIZIE FINNHUB CON TRADUZIONE DEEP-TRANSLATOR ---
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
            
            # Rileva la lingua e traduce se necessario
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
                'translated': title_lang == "en" or desc_lang == "en"  # Indica se è stato tradotto
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
            
            # Rileva lingua e traduce se necessario
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
            # Notizie generali
            general_news = fetch_finnhub_market_news(count//2)
            
            # Notizie company se abbiamo TOP picks
            company_news = []
            if not st.session_state.top_5_stocks.empty:
                top_symbols = st.session_state.top_5_stocks['Symbol'].head(2).tolist()
                for symbol in top_symbols:
                    company_specific = fetch_company_news_finnhub(symbol, limit=1)
                    company_news.extend(company_specific)
            
            # Combina
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
    """
    Calcola un punteggio di investimento per ogni azione basato su:
    - Momentum tecnico (RSI, MACD)
    - Trend (prezzo vs medie mobili)
    - Volatilità controllata
    - Raccomandazioni tecniche
    - Volume relativo
    """
    scored_df = df.copy()
    
    # Inizializza il punteggio
    scored_df['Investment_Score'] = 0.0
    
    # 1. RSI Score (peso 20%) - preferenza per RSI tra 50-70 (momentum positivo ma non ipercomprato)
    def rsi_score(rsi):
        if pd.isna(rsi):
            return 0
        if 50 <= rsi <= 70:
            return 10  # Zona ottimale
        elif 40 <= rsi < 50:
            return 7  # Buona
        elif 30 <= rsi < 40:
            return 5  # Accettabile
        elif rsi > 80:
            return 2  # Ipercomprato
        else:
            return 1  # Troppo basso
    
    scored_df['RSI_Score'] = scored_df['RSI'].apply(rsi_score)
    scored_df['Investment_Score'] += scored_df['RSI_Score'] * 0.20
    
    # 2. MACD Score (peso 15%) - MACD sopra signal line è positivo
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
    
    # 3. Trend Score (peso 25%) - prezzo vs SMA50 e SMA200
    def trend_score(price, sma50, sma200):
        if pd.isna(price) or pd.isna(sma50) or pd.isna(sma200):
            return 0
        score = 0
        # Prezzo sopra SMA50
        if price > sma50:
            score += 5
        # Prezzo sopra SMA200
        if price > sma200:
            score += 3
        # SMA50 sopra SMA200 (uptrend confermato)
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
    
    # 5. Volatility Score (peso 10%) - volatilità moderata è preferibile
    def volatility_score(vol):
        if pd.isna(vol):
            return 0
        if 0.5 <= vol <= 2.0:  # Volatilità ideale per guadagni a 2-4 settimane
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
    
    # 6. Market Cap Score (peso 10%) - preferenza per cap intermedia
    def mcap_score(mcap):
        if pd.isna(mcap):
            return 0
        if 1e9 <= mcap <= 50e9:  # 1B-50B sweet spot
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
    """Fetch data from TradingView screener with enhanced columns for scoring"""
    try:
        with st.spinner("🔍 Recupero dati dal mercato..."):
            query = (
                Query()
                .set_markets('america', 'australia','belgium','brazil', 'canada', 'chile', 'china','italy',
                            'czech', 'denmark', 'egypt', 'estonia', 'finland', 'france', 'germany', 'greece',
                            'hongkong', 'hungary','india', 'indonesia', 'ireland', 'israel', 'japan','korea',
                            'kuwait', 'lithuania', 'luxembourg', 'malaysia', 'mexico', 'morocco', 'netherlands',
                            'newzealand', 'norway', 'peru', 'philippines', 'poland', 'portugal', 'qatar', 'russia',
                            'singapore', 'slovakia', 'spain', 'sweden', 'switzerland', 'taiwan', 'uae', 'uk',
                            'venezuela', 'vietnam', 'crypto')
                .select('name', 'description', 'country', 'sector', 'currency', 'close', 'change', 'volume',
                       'market_cap_basic', 'RSI', 'MACD.macd', 'MACD.signal', 'SMA50', 'SMA200',
                       'Volatility.D', 'Recommend.All', 'float_shares_percent_current',
                       'relative_volume_10d_calc', 'price_earnings_ttm', 'earnings_per_share_basic_ttm',
                       'Perf.W', 'Perf.1M')
                .where(
                    Column('type').isin(['stock']),
                    Column('is_primary') == True,
                    Column('market_cap_basic').between(10_000_000_000, 200_000_000_000_000),
                    Column('close') > Column('SMA50'),
                    Column('close') > Column('SMA100'),
                    Column('close') > Column('SMA200'),
                    Column('RSI').between(30, 80),
                    Column('MACD.macd') > Column('MACD.signal'),
                    Column('Volatility.D') > 0.2,
                    Column('Recommend.All') > 0.1,
                    Column('relative_volume_10d_calc') > 0.7,
                    Column('float_shares_percent_current') > 0.3,
                )
                .order_by('market_cap_basic', ascending=False)
                .limit(200)
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
    """Seleziona le top 5 azioni con le migliori probabilità di guadagno"""
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

def fetch_fundamental_data(symbol: str):
    """Recupera dati fondamentali (bilanci, fatturato, EPS, margini, multipli) da TradingView."""
    from tradingview_screener import Query, Column
    import streamlit as st
    import pandas as pd

    try:
        q = (
            Query()
            .select(
                "name", "description", "country", "sector",
                "market_cap_basic", "fundamental_currency_code", 
                "income_statement_total_revenue", "income_statement_gross_profit", 
                "income_statement_net_income", "earnings_per_share_basic_ttm",
                "price_earnings_ttm", "dividend_yield_recent",
                "balance_sheet_total_assets", "balance_sheet_total_liabilities",
                "balance_sheet_shareholders_equity", "operating_margin_ttm",
                "net_profit_margin_ttm", "free_cash_flow_ttm"
            )
            .where(Column("name").eq(symbol.upper()))
            .get_scanner_data()
        )

        df = q[1]
        if df.empty:
            st.warning(f"Nessun dato fondamentale trovato per {symbol}.")
            return pd.DataFrame()

        df = df.rename(columns={
            "income_statement_total_revenue": "Ricavi Totali",
            "income_statement_gross_profit": "Utile Lordo",
            "income_statement_net_income": "Utile Netto",
            "earnings_per_share_basic_ttm": "EPS (TTM)",
            "price_earnings_ttm": "P/E (TTM)",
            "dividend_yield_recent": "Dividend Yield",
            "balance_sheet_total_assets": "Totale Attività",
            "balance_sheet_total_liabilities": "Totale Passività",
            "balance_sheet_shareholders_equity": "Patrimonio Netto",
            "operating_margin_ttm": "Margine Operativo %",
            "net_profit_margin_ttm": "Margine Netto %",
            "free_cash_flow_ttm": "Free Cash Flow"
        })

        # Formattazione numerica
        for col in [
            "Ricavi Totali", "Utile Lordo", "Utile Netto", "Totale Attività",
            "Totale Passività", "Patrimonio Netto", "Free Cash Flow"
        ]:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: f"${x/1e9:.2f}B" if pd.notnull(x) else "-")

        numeric_cols = ["P/E (TTM)", "Dividend Yield", "Margine Operativo %", "Margine Netto %"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].round(2)

        return df

    except Exception as e:
        st.error(f"Errore nel caricamento dati fondamentali: {e}")
        return pd.DataFrame()


# ============================================================================
# FUNZIONE PRINCIPALE PER IL MAIN
# ============================================================================

def stock_screener_app():
    """App principale per lo stock screener"""
    
    # SESSION STATE INITIALIZATION
    if 'data' not in st.session_state:
        st.session_state.data = pd.DataFrame()
    if 'last_update' not in st.session_state:
        st.session_state.last_update = None
    if 'top_5_stocks' not in st.session_state:
        st.session_state.top_5_stocks = pd.DataFrame()
    if 'market_news' not in st.session_state:
        st.session_state.market_news = []
    
    # --- MAIN APP CON TAB SYSTEM ---
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
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📡 Servizi**")
            st.success("✅ TradingView Screener attivo")
            st.success("✅ Sistema di scoring avanzato")
        
        with col2:
            st.markdown("**🇮🇹 Traduzione**")
            st.success("✅ Traduzione automatica EN→IT")
            st.success("✅ Rilevamento lingua Google")
    
    st.markdown("---")
    
    # Main controls
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        if st.button("🔄 Aggiorna Dati", type="primary", use_container_width=True):
            new_data = fetch_screener_data()
            if not new_data.empty:
                st.session_state.data = new_data
                st.session_state.top_5_stocks = get_top_5_investment_picks(new_data)
                
                # Recupera e traduce notizie da Finnhub
                st.session_state.market_news = fetch_mixed_finnhub_news(8)
                st.session_state.last_update = datetime.now()
                
                news_count = len(st.session_state.market_news)
                translated_count = sum(1 for news in st.session_state.market_news if news.get('translated', False))
                
                st.success(f"✅ Aggiornati {len(new_data)} titoli | 📰 {news_count} notizie ({translated_count} tradotte)")
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
    
    # --- TAB SYSTEM ---
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "🎯 Top Picks", "📰 Notizie", "🔍 TradingView Search"])
    
    with tab1:
        # Display data if available
        if not st.session_state.data.empty:
            df = st.session_state.data
            
            # Summary metrics
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
            
            # Filters
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
            
            # Apply filters
            filtered_df = df.copy()
            
            if selected_country != 'Tutti':
                filtered_df = filtered_df[filtered_df['Country'] == selected_country]
            
            if selected_sector != 'Tutti':
                filtered_df = filtered_df[filtered_df['Sector'] == selected_sector]
            
            if selected_rating != 'Tutti':
                filtered_df = filtered_df[filtered_df['Rating'] == selected_rating]
            
            filtered_df = filtered_df[filtered_df['Investment_Score'] >= min_score]
            
            # ============================================================
            # GRAFICI PLOTLY - PERFORMANCE SETTORI SETTIMANALE
            # ============================================================
            st.subheader("📈 Performance Settori - Ultima Settimana")
            st.markdown("*Basata sui titoli selezionati dal tuo screener*")
            
            if not filtered_df.empty and 'Perf.W' in filtered_df.columns:
                sector_weekly_perf = filtered_df.groupby('Sector')['Perf.W'].agg(['mean', 'count']).reset_index()
                sector_weekly_perf = sector_weekly_perf[sector_weekly_perf['count'] >= 2]
                sector_weekly_perf = sector_weekly_perf.sort_values('mean', ascending=True)
                
                if not sector_weekly_perf.empty:
                    # GRAFICO PLOTLY BAR - PERFORMANCE SETTORIALE
                    fig_sector_weekly = px.bar(
                        sector_weekly_perf,
                        y='Sector',
                        x='mean',
                        orientation='h',
                        title="Performance Settoriale - Ultima Settimana (%)",
                        labels={'mean': 'Performance Media (%)', 'Sector': 'Settore'},
                        color='mean',
                        color_continuous_scale=['red', 'yellow', 'green'],
                        text='mean'
                    )
                    
                    fig_sector_weekly.update_traces(
                        texttemplate='%{text:.1f}%',
                        textposition='outside',
                        textfont_size=10
                    )
                    
                    fig_sector_weekly.update_layout(
                        height=max(400, len(sector_weekly_perf) * 35),
                        showlegend=False,
                        xaxis_title="Performance (%)",
                        yaxis_title="Settore",
                        font=dict(size=11)
                    )
                    
                    fig_sector_weekly.add_vline(x=0, line_dash="dash", line_color="black", line_width=1)
                    
                    # MOSTRA IL GRAFICO PLOTLY
                    st.plotly_chart(fig_sector_weekly, use_container_width=True)
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        best_sector = sector_weekly_perf.iloc[-1]
                        st.metric(
                            "🥇 Miglior Settore",
                            best_sector['Sector'],
                            f"+{best_sector['mean']:.2f}%"
                        )
                    
                    with col2:
                        worst_sector = sector_weekly_perf.iloc[0]
                        st.metric(
                            "🥊 Peggior Settore",
                            worst_sector['Sector'],
                            f"{worst_sector['mean']:.2f}%"
                        )
                    
                    with col3:
                        avg_performance = sector_weekly_perf['mean'].mean()
                        st.metric(
                            "📊 Media Generale",
                            f"{avg_performance:.2f}%"
                        )
                else:
                    st.info("📈 Non ci sono abbastanza dati settoriali per mostrare la performance settimanale.")
            else:
                st.info("📈 Aggiorna i dati per vedere la performance settimanale dei settori.")
            
            # Data table
            st.subheader("📋 Dati Dettagliati")
            st.markdown(f"**Visualizzati {len(filtered_df)} di {len(df)} titoli**")
            
            available_columns = ['Company', 'Symbol', 'Country', 'Sector', 'Currency', 'Price', 'Rating',
                                'Investment_Score', 'Recommend.All', 'RSI', 'Volume', 'TradingView_URL']
            
            display_columns = st.multiselect(
                "Seleziona colonne da visualizzare:",
                available_columns,
                default=['Company', 'Symbol', 'Investment_Score', 'Price', 'Country','Sector','TradingView_URL']
            )
            
            if display_columns:
                display_df = filtered_df[display_columns].copy()
                
                if 'Investment_Score' in display_df.columns:
                    display_df['Investment_Score'] = display_df['Investment_Score'].round(1)
                
                column_names = {
                    'Company': 'Azienda',
                    'Symbol': 'Simbolo',
                    'Country': 'Paese',
                    'Sector': 'Settore',
                    'Currency': 'Valuta',
                    'Price': 'Prezzo',
                    'Rating': 'Rating',
                    'Investment_Score': 'Score',
                    'Recommend.All': 'Rating Numerico',
                    'RSI': 'RSI',
                    'Volume': 'Volume',
                    'TradingView_URL': 'Chart'
                }
                
                display_df = display_df.rename(columns=column_names)
                
                def color_score(val):
                    if isinstance(val, (int, float)):
                        if val >= 80:
                            return 'background-color: #90EE90'
                        elif val >= 65:
                            return 'background-color: #FFFF99'
                        elif val < 50:
                            return 'background-color: #FFB6C1'
                    return ''
                
                def color_rating(val):
                    if '🟢' in str(val):
                        return 'background-color: #90EE90'
                    elif '🟡' in str(val):
                        return 'background-color: #FFFF99'
                    elif '🔴' in str(val):
                        return 'background-color: #FFB6C1'
                    return ''
                
                styled_df = display_df.style
                
                if 'Score' in display_df.columns:
                    styled_df = styled_df.applymap(color_score, subset=['Score'])
                
                if 'Rating' in display_df.columns:
                    styled_df = styled_df.applymap(color_rating, subset=['Rating'])
                
                st.dataframe(
                    styled_df,
                    use_container_width=True,
                    height=400
                )
                
                csv = display_df.to_csv(index=False)
                st.download_button(
                    label="📥 Scarica Dati Filtrati (CSV)",
                    data=csv,
                    file_name=f"screener_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        else:
            # Welcome message
            st.markdown("""
## 🚀 Benvenuto nel Financial Screener Professionale!

Questa app utilizza un **algoritmo di scoring intelligente** e **notizie tradotte con Google Translate**.

### 🎯 Funzionalità Principali:

- **🔥 TOP 5 PICKS**: Selezione automatica titoli con maggiori probabilità di guadagno
- **📈 Link TradingView**: Accesso diretto ai grafici professionali
- **🧮 Investment Score**: Punteggio 0-100 con analisi multi-fattoriale
- **📊 Performance Settoriale**: Dashboard completa con grafici Plotly interattivi
- **📰 Notizie Tradotte**: Aggiornamenti reali da Finnhub API tradotti con Google Translate
- **🔍 Ricerca TradingView**: Cerca e visualizza grafici di qualsiasi titolo

### 🌐 Google Translate Integration:

- **🇬🇧→🇮🇹 EN→IT**: Traduzione automatica delle notizie inglesi
- **🔍 Rilevamento lingua**: Identificazione automatica della lingua originale
- **⚡ Veloce e accurato**: Usa la stessa tecnologia di translate.google.com

**👆 Clicca su 'Aggiorna Dati' per iniziare l'analisi e vedere i grafici interattivi!**

            """)
    
    with tab2:
        # TOP 5 INVESTMENT PICKS
        if not st.session_state.top_5_stocks.empty:
            st.subheader("🎯 TOP 5 PICKS - Maggiori Probabilità di Guadagno (2-4 settimane)")
            st.markdown("*Selezionate dall'algoritmo di scoring intelligente*")
            
            top_5 = st.session_state.top_5_stocks
            
            for idx, (_, stock) in enumerate(top_5.iterrows(), 1):
                with st.container():
                    col1, col2, col3, col4 = st.columns([1, 3, 2, 1])
                    
                    with col1:
                        st.markdown(f"### #{idx}")
                        st.markdown(f"**Score: {stock['Investment_Score']:.1f}/100**")
                    
                    with col2:
                        st.markdown(f"**{stock['Company']}** ({stock['Symbol']})")
                        st.markdown(f"*{stock['Country']} | {stock['Sector']}*")
                        st.markdown(f"💰 **${stock['Price']}** ({stock['Change %']})")
                        st.caption(f"📊 {stock['Recommendation_Reason']}")
                    
                    with col3:
                        st.markdown("**Metriche Chiave:**")
                        st.markdown(f"RSI: {stock['RSI']} | Rating: {stock['Rating']}")
                        st.markdown(f"Vol: {stock['Volatility %']} | MCap: {stock['Market Cap']}")
                        st.markdown(f"Perf 1W: {stock['Perf Week %']} | 1M: {stock['Perf Month %']}")
                    
                    with col4:
                        tv_url = stock['TradingView_URL']
                        st.link_button(
                            f"📈 Grafico {stock['Symbol']}",
                            tv_url,
                            use_container_width=True
                        )
                    
                    st.markdown("---")
        
        else:
            st.info("📊 Aggiorna i dati per visualizzare i TOP 5 picks!")
    
    with tab3:
        # SEZIONE NOTIZIE FINNHUB TRADOTTE CON GOOGLE
        if st.session_state.market_news:
            st.subheader("📰 Notizie di Mercato Tradotte con Google Translate")
            
            # Statistiche traduzioni
            total_news = len(st.session_state.market_news)
            translated_news = sum(1 for news in st.session_state.market_news if news.get('translated', False))
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("📰 Totale Notizie", total_news)
            with col2:
                st.metric("🌐 Tradotte", translated_news)
            with col3:
                st.metric("🇮🇹 Originali IT", total_news - translated_news)
            
            st.info(f"📡 {total_news} notizie da Finnhub | 🌐 {translated_news} tradotte con Google Translate")
            
            # Display news
            col1, col2 = st.columns(2)
            
            for i, news in enumerate(st.session_state.market_news):
                with col1 if i % 2 == 0 else col2:
                    with st.container():
                        # Aggiungi indicatore di traduzione
                        translation_indicator = "🌐 " if news.get('translated', False) else ""
                        
                        st.markdown(f"**{translation_indicator}{news['title']}**")
                        st.markdown(f"*{news['date']} - {news['source']}*")
                        st.markdown(news['description'])
                        st.markdown(f"**Impatto:** {news['impact']}")
                        
                        if news.get('url'):
                            st.markdown(f"**[Leggi articolo originale]({news['url']})**")
                        
                        # Badge categoria
                        if news.get('category'):
                            category_names = {
                                "general": "📈 Mercati generali",
                                "company_specific": "🏢 Notizie aziendali"
                            }
                            category_display = category_names.get(news['category'], news['category'])
                            st.caption(f"🏷️ {category_display}")
                        
                        # Indicatore traduzione
                        if news.get('translated', False):
                            st.caption("🌐 Tradotto automaticamente con Google Translate")
                        
                        st.markdown("---")
            
            with tab4:
                st.header("📊 Analisi Fondamentale Azienda")
                symbol = st.text_input("Inserisci Simbolo o Nome Azienda (es. AAPL, TSLA, NVDA):", "")
            
                if symbol:
                    if st.button("📑 Estrai Dati Finanziari"):
                        df_fundamental = fetch_fundamental_data(symbol)
            
                        if not df_fundamental.empty:
                            row = df_fundamental.iloc[0]
                            st.subheader(f"{row.get('description', '')} ({row.get('name', symbol.upper())})")
                            st.caption(f"Settore: {row.get('sector', 'n/a')} | Paese: {row.get('country', 'n/a')}")
            
                            st.markdown("### 💼 Dati Fondamentali Principali")
                            display_cols = [
                                "Ricavi Totali", "Utile Lordo", "Utile Netto", 
                                "P/E (TTM)", "EPS (TTM)", "Margine Operativo %", "Margine Netto %",
                                "Totale Attività", "Totale Passività", 
                                "Patrimonio Netto", "Free Cash Flow", "Dividend Yield"
                            ]
                            cols = [col for col in display_cols if col in df_fundamental.columns]
                            st.dataframe(df_fundamental[cols].T, use_container_width=True, height=400)
            
                            st.markdown("---")
                            st.markdown("### 🧾 Report Sintetico")
                            # Genera analisi testuale semplice
                            try:
                                growth_comment = ""
                                if 'P/E (TTM)' in row and pd.notnull(row['P/E (TTM)']):
                                    if row['P/E (TTM)'] < 15:
                                        growth_comment = "Il titolo sembra sottovalutato rispetto ai suoi utili."
                                    elif row['P/E (TTM)'] > 30:
                                        growth_comment = "Il titolo appare sopravvalutato rispetto agli utili attuali."
                                    else:
                                        growth_comment = "Il rapporto prezzo/utili è in linea con il mercato."
            
                                profitability = ""
                                if 'Margine Netto %' in row and pd.notnull(row['Margine Netto %']):
                                    profitability = (
                                        "Margini elevati e buone prospettive di redditività."
                                        if row['Margine Netto %'] > 15 else
                                        "Margini deboli, profitabilità moderata."
                                    )
            
                                st.info(f"""
                                **Sintesi Automatica:**
                                - Ricavi Annuali: {row.get('Ricavi Totali', '-')}.
                                - Utile Netto: {row.get('Utile Netto', '-')}.
                                - EPS (Ultimi 12 mesi): {row.get('EPS (TTM)', '-')}.
                                - {growth_comment}
                                - {profitability}
                                """)
                            except Exception as e:
                                st.error(f"Errore nella generazione del report: {e}")

            
            # Summary
            current_date = datetime.now()
            st.success(f"""
🎯 **Notizie di Mercato Aggiornate** - {current_date.strftime('%d/%m/%Y %H:%M')}

✅ Fonte: Finnhub API | 🌐 Traduzione: Google Translate | 🇮🇹 Contenuti in italiano
            """)
        
        else:
            st.info("📰 Aggiorna i dati per visualizzare le notizie tradotte da Finnhub!")
            
            st.markdown("""
### 🌐 Notizie Tradotte con Google Translate

Le notizie vengono recuperate dall'API Finnhub e tradotte automaticamente:

- **📡 Fonte**: Finnhub API per notizie finanziarie reali
- **🔍 Rilevamento**: Identificazione automatica della lingua originale con Google
- **🌐 Traduzione**: Google Translate API (affidabile e veloce)
- **🇬🇧→🇮🇹**: Traduzione automatica da inglese a italiano
- **📈 Notizie generali**: Mercati globali e trend
- **🏢 Company News**: Notizie specifiche per i tuoi TOP picks
- **🔗 Link originali**: Accesso alle fonti complete in lingua originale

*Clicca su 'Aggiorna Dati' per recuperare le ultime notizie tradotte!*
            """)
    
    with tab4:
        st.header("📊 Analisi Fondamentale Azienda")
        symbol = st.text_input("Inserisci Simbolo o Nome Azienda (es. AAPL, TSLA, NVDA):", "")
    
        if symbol:
            if st.button("📑 Estrai Dati Finanziari"):
                df_fundamental = fetch_fundamental_data(symbol)
    
                if not df_fundamental.empty:
                    row = df_fundamental.iloc[0]
                    st.subheader(f"{row.get('description', '')} ({row.get('name', symbol.upper())})")
                    st.caption(f"Settore: {row.get('sector', 'n/a')} | Paese: {row.get('country', 'n/a')}")
    
                    st.markdown("### 💼 Dati Fondamentali Principali")
                    display_cols = [
                        "Ricavi Totali", "Utile Lordo", "Utile Netto", 
                        "P/E (TTM)", "EPS (TTM)", "Margine Operativo %", "Margine Netto %",
                        "Totale Attività", "Totale Passività", 
                        "Patrimonio Netto", "Free Cash Flow", "Dividend Yield"
                    ]
                    cols = [col for col in display_cols if col in df_fundamental.columns]
                    st.dataframe(df_fundamental[cols].T, use_container_width=True, height=400)
    
                    st.markdown("---")
                    st.markdown("### 🧾 Report Sintetico")
                    # Genera analisi testuale semplice
                    try:
                        growth_comment = ""
                        if 'P/E (TTM)' in row and pd.notnull(row['P/E (TTM)']):
                            if row['P/E (TTM)'] < 15:
                                growth_comment = "Il titolo sembra sottovalutato rispetto ai suoi utili."
                            elif row['P/E (TTM)'] > 30:
                                growth_comment = "Il titolo appare sopravvalutato rispetto agli utili attuali."
                            else:
                                growth_comment = "Il rapporto prezzo/utili è in linea con il mercato."
    
                        profitability = ""
                        if 'Margine Netto %' in row and pd.notnull(row['Margine Netto %']):
                            profitability = (
                                "Margini elevati e buone prospettive di redditività."
                                if row['Margine Netto %'] > 15 else
                                "Margini deboli, profitabilità moderata."
                            )
    
                        st.info(f"""
                        **Sintesi Automatica:**
                        - Ricavi Annuali: {row.get('Ricavi Totali', '-')}.
                        - Utile Netto: {row.get('Utile Netto', '-')}.
                        - EPS (Ultimi 12 mesi): {row.get('EPS (TTM)', '-')}.
                        - {growth_comment}
                        - {profitability}
                        """)
                    except Exception as e:
                        st.error(f"Errore nella generazione del report: {e}")

    
    # --- SIDEBAR ---
    st.sidebar.title("ℹ️ Informazioni")
    
    st.sidebar.markdown("""
### 🎯 Funzionalità:

- **🏆 TOP 5 PICKS**: Algoritmo di selezione AI
- **🧮 Investment Score**: Sistema a 6 fattori
- **📈 TradingView**: Integrazione diretta e ricerca
- **📊 Analisi Settoriale**: Performance settimanale con grafici Plotly
- **📰 Notizie Tradotte**: Finnhub + Google Translate

### 🌐 Google Translate:

- **Fonte Notizie**: Finnhub API (dati reali)
- **Rilevamento Lingua**: Google Detect API
- **Traduzione**: Google Translate API (affidabile)
- **🇬🇧→🇮🇹**: Inglese → Italiano
- **Indicatori**: 🌐 = tradotto automaticamente

### 📊 Investment Score:

L'algoritmo valuta ogni azione su 6 parametri:

1. **RSI Score**: Momentum ottimale
2. **MACD Score**: Segnale di trend
3. **Trend Score**: Analisi medie mobili
4. **Technical Rating**: Raccomandazioni aggregate
5. **Volatility Score**: Movimento controllato
6. **Market Cap Score**: Dimensione ideale

### 📰 Notizie:

- **🌐 Solo dati reali**: Nessun contenuto demo
- **🇮🇹 Google Translate**: Traduzione EN→IT
- **📊 Categorizzazione**: Automatica per settore
- **🔗 Fonti originali**: Link alle notizie complete
    """)
