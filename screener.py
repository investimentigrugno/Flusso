# screener.py - Stock Screener completo
# COPIA QUESTO FILE COMPLETAMENTE E SOSTITUISCI IL TUO screener.py

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
from ai_agent import call_groq_api, escape_markdown_latex
import yfinance as yf
import ta

# ============================================================================
# SEZIONE 1: FUNZIONI FORMATTAZIONE
# ============================================================================

def format_technical_rating(rating: float) -> str:
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
    if pd.isna(value) or value is None:
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
    if pd.isna(value):
        return "N/A"
    return f"{value*100:.2f}%"

# ============================================================================
# SEZIONE 2: FUNZIONI TRADINGVIEW SCREENER (TAB 1 E 2)
# ============================================================================

def calculate_investment_score(df):
    scored_df = df.copy()
    scored_df['Investment_Score'] = 0.0
    
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
    
    max_possible_score = 10 * (0.20 + 0.15 + 0.25 + 0.20 + 0.10 + 0.10)
    scored_df['Investment_Score'] = (scored_df['Investment_Score'] / max_possible_score) * 100
    scored_df['Investment_Score'] = scored_df['Investment_Score'].round(1)
    
    return scored_df

def get_tradingview_url(symbol):
    if ':' in symbol:
        clean_symbol = symbol.split(':')[1]
    else:
        clean_symbol = symbol
    return f"https://www.tradingview.com/chart/?symbol={symbol}"

def fetch_screener_data():
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
                    Column('type').isin(['stock','etf']),
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
            )
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
                df = df.rename(columns={
                    'name': 'Symbol',
                    'description': 'Company',
                    'country': 'Country',
                    'sector': 'Sector',
                    'currency': 'Currency'
                })
                return df
        return pd.DataFrame()
    
    except Exception as e:
        st.error(f"❌ Errore nel recupero dati: {e}")
        return pd.DataFrame()

def get_top_5_investment_picks(df):
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

# ============================================================================
# SEZIONE 3: FUNZIONI YFINANCE (TAB 3)
# ============================================================================

def fetch_yfinance_data(ticker_symbol, period="1y"):
    try:
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period=period)
        info = stock.info
        news = stock.news[:5] if hasattr(stock, 'news') else []
        return {'history': hist, 'info': info, 'news': news, 'ticker': stock, 'symbol': ticker_symbol}
    except Exception as e:
        st.error(f"❌ Errore nel caricamento dati: {e}")
        return None

def calculate_atr(high, low, close, period=14):
    try:
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr
    except:
        return None

def calculate_volatility(close, period=20):
    try:
        returns = close.pct_change()
        volatility = returns.rolling(window=period).std() * np.sqrt(252)
        return volatility
    except:
        return None

def calculate_bollinger_bands(close, period=20, num_std=2):
    try:
        sma = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        upper_band = sma + (std * num_std)
        lower_band = sma - (std * num_std)
        bandwidth = (upper_band - lower_band) / sma
        return upper_band, sma, lower_band, bandwidth
    except:
        return None, None, None, None

def calculate_rsi(close, period=14):
    try:
        return ta.momentum.rsi(close, length=period)
    except:
        return None

def calculate_macd_diff(close, fast=12, slow=26):
    try:
        return ta.trend.macd_diff(close, fast=fast, slow=slow)
    except:
        return None

def calculate_dynamic_trading_signals(data, atr_multiplier_sl=2.0, atr_multiplier_tp=3.5):
    try:
        close = data['Close']
        high = data['High']
        low = data['Low']
        volume = data['Volume']
        
        rsi = calculate_rsi(close)
        macd = calculate_macd_diff(close)
        atr = calculate_atr(high, low, close, period=14)
        volatility = calculate_volatility(close, period=20)
        bb_upper, bb_middle, bb_lower, bb_bandwidth = calculate_bollinger_bands(close)
        
        current_price = close.iloc[-1]
        latest_rsi = rsi.iloc[-1] if rsi is not None else 50
        latest_macd = macd.iloc[-1] if macd is not None else 0
        latest_atr = atr.iloc[-1] if atr is not None else current_price * 0.02
        latest_volatility = volatility.iloc[-1] if volatility is not None else 0.3
        latest_bb_upper = bb_upper.iloc[-1] if bb_upper is not None else current_price * 1.05
        latest_bb_lower = bb_lower.iloc[-1] if bb_lower is not None else current_price * 0.95
        latest_bb_middle = bb_middle.iloc[-1] if bb_middle is not None else current_price
        latest_bandwidth = bb_bandwidth.iloc[-1] if bb_bandwidth is not None else 0.1
        
        support = latest_bb_lower
        resistance = latest_bb_upper
        
        avg_volume = volume.rolling(window=20).mean().iloc[-1]
        volume_ratio = volume.iloc[-1] / avg_volume if avg_volume > 0 else 1.0
        
        signal = {'direction': 'HOLD', 'confidence': 0.0, 'entry_point': current_price, 'stop_loss': current_price, 'take_profit': current_price,
                  'rsi': latest_rsi, 'macd': latest_macd, 'atr': latest_atr, 'volatility': latest_volatility * 100,
                  'support': support, 'resistance': resistance, 'bb_bandwidth': latest_bandwidth * 100,
                  'volume_ratio': volume_ratio, 'risk_reward_ratio': 0.0}
        
        buy_conditions = 0
        buy_confidence = 0.0
        
        if latest_rsi < 30:
            buy_conditions += 1
            buy_confidence += 0.25
        if current_price <= latest_bb_lower * 1.02:
            buy_conditions += 1
            buy_confidence += 0.20
        if latest_macd > 0:
            buy_conditions += 1
            buy_confidence += 0.15
        if volume_ratio > 1.2:
            buy_conditions += 1
            buy_confidence += 0.15
        if latest_volatility < 0.5:
            buy_confidence += 0.10
        
        sell_conditions = 0
        sell_confidence = 0.0
        
        if latest_rsi > 70:
            sell_conditions += 1
            sell_confidence += 0.25
        if current_price >= latest_bb_upper * 0.98:
            sell_conditions += 1
            sell_confidence += 0.20
        if latest_macd < 0:
            sell_conditions += 1
            sell_confidence += 0.15
        if volume_ratio > 1.2:
            sell_conditions += 1
            sell_confidence += 0.15
        
        if buy_conditions >= 2:
            signal['direction'] = 'BUY'
            signal['confidence'] = min(buy_confidence, 0.95)
            signal['entry_point'] = max(support * 1.005, current_price * 0.998)
            sl_distance = latest_atr * atr_multiplier_sl
            tp_distance = latest_atr * atr_multiplier_tp
            signal['stop_loss'] = signal['entry_point'] - sl_distance
            signal['take_profit'] = signal['entry_point'] + tp_distance
            if signal['take_profit'] > resistance:
                signal['take_profit'] = resistance * 0.99
        elif sell_conditions >= 2:
            signal['direction'] = 'SELL'
            signal['confidence'] = min(sell_confidence, 0.95)
            signal['entry_point'] = min(resistance * 0.995, current_price * 1.002)
            sl_distance = latest_atr * atr_multiplier_sl
            tp_distance = latest_atr * atr_multiplier_tp
            signal['stop_loss'] = signal['entry_point'] + sl_distance
            signal['take_profit'] = signal['entry_point'] - tp_distance
            if signal['take_profit'] < support:
                signal['take_profit'] = support * 1.01
        else:
            signal['direction'] = 'HOLD'
            signal['confidence'] = 0.3
            signal['entry_point'] = current_price
            sl_distance = latest_atr * 1.5
            tp_distance = latest_atr * 2.5
            signal['stop_loss'] = current_price - sl_distance
            signal['take_profit'] = current_price + tp_distance
        
        if signal['direction'] == 'BUY':
            risk = signal['entry_point'] - signal['stop_loss']
            reward = signal['take_profit'] - signal['entry_point']
        elif signal['direction'] == 'SELL':
            risk = signal['stop_loss'] - signal['entry_point']
            reward = signal['entry_point'] - signal['take_profit']
        else:
            risk = abs(signal['entry_point'] - signal['stop_loss'])
            reward = abs(signal['take_profit'] - signal['entry_point'])
        
        signal['risk_reward_ratio'] = reward / risk if risk > 0 else 0.0
        signal['atr_percent'] = (latest_atr / current_price) * 100
        signal['sl_distance_percent'] = (abs(signal['entry_point'] - signal['stop_loss']) / signal['entry_point']) * 100
        signal['tp_distance_percent'] = (abs(signal['take_profit'] - signal['entry_point']) / signal['entry_point']) * 100
        
        return signal
    
    except Exception as e:
        st.error(f"Errore nel calcolo dei segnali: {e}")
        return None

# ============================================================================
# SEZIONE 4: MAIN FUNCTION stock_screener_app()
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
    if 'last_analyzed_ticker' not in st.session_state:
        st.session_state.last_analyzed_ticker = None
    
    st.title("📈 Financial Screener Dashboard")
    st.markdown("Analizza le migliori opportunità di investimento con criteri tecnici avanzati")
    
    # Main controls
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("🔄 Aggiorna Dati", type="primary", use_container_width=True):
            new_data = fetch_screener_data()
            if not new_data.empty:
                st.session_state.data = new_data
                st.session_state.top_5_stocks = get_top_5_investment_picks(new_data)
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
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard TradingView", "🎯 Top Picks", "🔍 Analisi yfinance"])
    
    # ========== TAB 1: DASHBOARD ==========
    with tab1:
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
                st.dataframe(display_df, use_container_width=True, height=400)
                
                csv = display_df.to_csv(index=False)
                st.download_button(
                    label="📥 Scarica Dati Filtrati (CSV)",
                    data=csv,
                    file_name=f"screener_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.markdown("""
            ## 🚀 Benvenuto nel Financial Screener Professionale!
            **👆 Clicca su 'Aggiorna Dati' per iniziare l'analisi!**
            """)
    
    # ========== TAB 2: TOP PICKS ==========
    with tab2:
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
                    with col4:
                        tv_url = stock['TradingView_URL']
                        st.link_button(
                            f"📈 Grafico",
                            tv_url,
                            use_container_width=True
                        )
                
                st.markdown("---")
        else:
            st.info("📊 Aggiorna i dati per visualizzare i TOP 5 picks!")
    
    # ========== TAB 3: YFINANCE ANALYSIS ==========
    with tab3:
        st.subheader("🔍 Analisi Multi-Agente Avanzata (yfinance)")
        st.markdown("Cerca un ticker e ottieni analisi completa con Entry/SL/TP basati su volatilità")
        
        col1, col2 = st.columns([4, 1])
        with col1:
            ticker_input = st.text_input(
                "🔍 Inserisci ticker (es. AAPL, MSFT, TSLA):",
                value="",
                key="yfinance_ticker_search",
                placeholder="Inserisci simbolo ticker..."
            )
        with col2:
            st.markdown("")
            search_btn = st.button("🔎 Cerca", type="primary", use_container_width=True)
        
        st.markdown("**💡 Ticker comuni:**")
        col1, col2, col3, col4, col5 = st.columns(5)
        quick_tickers = [("🍎 AAPL", "AAPL"), ("🚗 TSLA", "TSLA"), ("🤖 MSFT", "MSFT"), ("💎 BRK.A", "BRK.A"), ("📱 META", "META")]
        for i, (label, ticker_val) in enumerate(quick_tickers):
            with [col1, col2, col3, col4, col5][i]:
                if st.button(label, key=f"quick_ticker_{i}", use_container_width=True):
                    ticker_input = ticker_val
                    search_btn = True
        
        if (ticker_input and search_btn) or st.session_state.get("last_analyzed_ticker") != ticker_input.upper():
            if ticker_input.strip():
                st.session_state["last_analyzed_ticker"] = ticker_input.upper()
                
                with st.spinner(f"📊 Analisi di {ticker_input.upper()} in corso..."):
                    ticker_data = fetch_yfinance_data(ticker_input.upper(), period="1y")
                    
                    if ticker_data and ticker_data['info']:
                        info = ticker_data['info']
                        current_price = ticker_data['history']['Close'].iloc[-1] if len(ticker_data['history']) > 0 else 0
                        
                        # Metriche generali
                        st.markdown("---")
                        st.subheader("📈 Informazioni Generali")
                        
                        col1, col2, col3, col4, col5 = st.columns(5)
                        with col1:
                            st.metric("💰 Prezzo Attuale", f"{current_price:.2f}")
                        with col2:
                            market_cap = info.get('marketCap')
                            if market_cap and market_cap >= 1e9:
                                st.metric("🏦 Market Cap", f"{market_cap/1e9:.2f}B")
                            else:
                                st.metric("🏦 Market Cap", "N/A")
                        with col3:
                            pe_ratio = info.get('trailingPE')
                            st.metric("📊 P/E Ratio", f"{pe_ratio:.2f}" if pe_ratio else "N/A")
                        with col4:
                            div_yield = info.get('dividendYield')
                            if div_yield:
                                st.metric("💵 Div Yield", f"{div_yield*100:.2f}%")
                            else:
                                st.metric("💵 Div Yield", "N/A")
                        with col5:
                            beta = info.get('beta')
                            st.metric("📉 Beta", f"{beta:.2f}" if beta else "N/A")
                        
                        # Analisi tecnica
                        st.markdown("---")
                        st.subheader("🎯 Analisi Tecnica Avanzata (ATR-based)")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            atr_sl = st.slider("ATR Multiplier SL", min_value=1.0, max_value=4.0, value=2.0, step=0.5, help="Quanti ATR per Stop Loss")
                        with col2:
                            atr_tp = st.slider("ATR Multiplier TP", min_value=1.5, max_value=6.0, value=3.5, step=0.5, help="Quanti ATR per Take Profit")
                        with col3:
                            period_selection = st.selectbox("Periodo Analisi", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=2)
                        
                        signal = calculate_dynamic_trading_signals(ticker_data['history'], atr_multiplier_sl=atr_sl, atr_multiplier_tp=atr_tp)
                        
                        if signal:
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                color_emoji = "🟢" if signal['direction'] == "BUY" else "🔴" if signal['direction'] == "SELL" else "🟡"
                                st.metric(f"{color_emoji} Segnale Finale", signal['direction'], f"{signal['confidence']*100:.0f}% confidence")
                            with col2:
                                st.metric("📊 ATR (Volatilità)", f"{signal['atr']:.2f}", f"{signal['atr_percent']:.2f}% del prezzo")
                            with col3:
                                st.metric("📈 Volatilità Storica", f"{signal['volatility']:.1f}%", "Annualizzata")
                            with col4:
                                rr_status = "✅ Ottimo" if signal['risk_reward_ratio'] >= 2.0 else "⚠️ Accettabile"
                                st.metric("Risk/Reward", f"1:{signal['risk_reward_ratio']:.2f}", rr_status)
                            
                            st.markdown("### 📍 Livelli di Trading (Basati su ATR)")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.markdown(f"**Entry Point:**")
                                st.markdown(f"# `{signal['entry_point']:.2f}`")
                            with col2:
                                st.markdown(f"**Stop Loss (SL):**")
                                st.markdown(f"# `{signal['stop_loss']:.2f}`")
                                st.caption(f"📉 -{signal['sl_distance_percent']:.2f}%")
                            with col3:
                                st.markdown(f"**Take Profit (TP):**")
                                st.markdown(f"# `{signal['take_profit']:.2f}`")
                                st.caption(f"📈 +{signal['tp_distance_percent']:.2f}%")
                        else:
                            st.error("❌ Errore nel calcolo dei segnali")
                        
                        # Notizie
                        st.markdown("---")
                        st.subheader("📰 Ultime Notizie")
                        if ticker_data['news']:
                            for i, news in enumerate(ticker_data['news'][:3], 1):
                                with st.expander(f"📰 Notizia {i}"):
                                    if isinstance(news, dict):
                                        st.write(f"**Titolo:** {news.get('title', 'N/A')}")
                                        st.write(f"**Link:** {news.get('link', 'N/A')}")
                        else:
                            st.info("📰 Nessuna notizia disponibile")
                        
                        # ============================================================
                        # MULTI-AGENT AI ANALYSIS - INSERIRE QUI
                        # ============================================================
                        
                        # ============================================================================
                        # SEZIONE: 3 AGENTI AI CHE SI CONFRONTANO - MULTI-AGENT ANALYSIS
                        # ============================================================================
                        
                        def generate_technical_agent_analysis(signal: dict, ticker_symbol: str) -> str:
                            """
                            AGENTE 1: ANALISTA TECNICO
                            Analizza indicatori tecnici, volatilità, trends
                            """
                            prompt = f"""
                            Sei un esperto di Analisi Tecnica. Analizza il seguente titolo {ticker_symbol}:
                            
                            DATI TECNICI:
                            - Segnale: {signal['direction']}
                            - Confidenza: {signal['confidence']*100:.0f}%
                            - Prezzo: ${signal['entry_point']:.2f}
                            - RSI: {signal['rsi']:.1f}
                            - MACD: {signal['macd']:.4f}
                            - ATR (Volatilità): ${signal['atr']:.2f} ({signal['atr_percent']:.2f}%)
                            - Volatilità Annualizzata: {signal['volatility']:.1f}%
                            - Support: ${signal['support']:.2f}
                            - Resistance: ${signal['resistance']:.2f}
                            - Volume Ratio: {signal['volume_ratio']:.2f}x
                            - Risk/Reward: 1:{signal['risk_reward_ratio']:.2f}
                            
                            LIVELLI DI TRADING (Basati su ATR):
                            - Entry: ${signal['entry_point']:.2f}
                            - Stop Loss: ${signal['stop_loss']:.2f} (-{signal['sl_distance_percent']:.2f}%)
                            - Take Profit: ${signal['take_profit']:.2f} (+{signal['tp_distance_percent']:.2f}%)
                            
                            Fornisci un'analisi BREVE (max 200 parole) su:
                            1. Interpretazione del segnale tecnico
                            2. Qualità della volatilità (controllata? Eccessiva?)
                            3. Valutazione del Risk/Reward
                            4. Raccomandazione su Entry/Exit
                            5. RATING TECNICO: Strong Buy / Buy / Hold / Sell (1 sola riga)
                            """
                            
                            try:
                                response = call_groq_api(prompt, max_tokens=400)
                                return response
                            except Exception as e:
                                return f"❌ Errore nell'analisi tecnica: {str(e)}"
                        
                        def generate_fundamental_agent_analysis(ticker_ dict, ticker_symbol: str) -> str:
                            """
                            AGENTE 2: ANALISTA FONDAMENTALE
                            Analizza metriche fondamentali, crescita, solidità finanziaria
                            """
                            info = ticker_data['info']
                            
                            pe = info.get('trailingPE', 'N/A')
                            peg = info.get('pegRatio', 'N/A')
                            pb = info.get('priceToBook', 'N/A')
                            roe = info.get('returnOnEquity', 'N/A')
                            roa = info.get('returnOnAssets', 'N/A')
                            profit_margin = info.get('profitMargins', 'N/A')
                            rev_growth = info.get('revenueGrowth', 'N/A')
                            eps_growth = info.get('earningsGrowth', 'N/A')
                            fcf = info.get('freeCashflow', 'N/A')
                            debt_equity = info.get('debtToEquity', 'N/A')
                            current_ratio = info.get('currentRatio', 'N/A')
                            div_yield = info.get('dividendYield', 'N/A')
                            market_cap = info.get('marketCap', 'N/A')
                            
                            prompt = f"""
                            Sei un esperto di Analisi Fondamentale. Analizza il titolo {ticker_symbol}:
                            
                            METRICHE DI VALUTAZIONE:
                            - P/E Ratio: {pe}
                            - PEG Ratio: {peg}
                            - Price/Book: {pb}
                            - Market Cap: {market_cap}
                            
                            REDDITIVITÀ:
                            - ROE: {roe}
                            - ROA: {roa}
                            - Profit Margin: {profit_margin}
                            
                            CRESCITA:
                            - Revenue Growth: {rev_growth}
                            - EPS Growth: {eps_growth}
                            - Free Cash Flow: {fcf}
                            
                            SOLIDITÀ FINANZIARIA:
                            - Debt/Equity: {debt_equity}
                            - Current Ratio: {current_ratio}
                            - Dividend Yield: {div_yield}
                            
                            Fornisci un'analisi BREVE (max 200 parole) su:
                            1. Valutazione dell'azione (sottovalutata/equa/sopravvalutata)
                            2. Salute della crescita (sostenibile?)
                            3. Solidità finanziaria e liquidità
                            4. Qualità degli utili
                            5. RATING FONDAMENTALE: Strong Buy / Buy / Hold / Sell (1 sola riga)
                            """
                            
                            try:
                                response = call_groq_api(prompt, max_tokens=400)
                                return response
                            except Exception as e:
                                return f"❌ Errore nell'analisi fondamentale: {str(e)}"
                        
                        def generate_news_sentiment_agent_analysis(ticker_ dict, ticker_symbol: str) -> str:
                            """
                            AGENTE 3: ANALISTA NEWS & SENTIMENT
                            Analizza ultime notizie e sentiment di mercato
                            """
                            news_list = ticker_data.get('news', [])
                            
                            news_text = ""
                            if news_list:
                                for i, news in enumerate(news_list[:5], 1):
                                    if isinstance(news, dict):
                                        title = news.get('title', 'N/A')
                                        news_text += f"{i}. {title}\n"
                            else:
                                news_text = "Nessuna notizia disponibile"
                            
                            prompt = f"""
                            Sei un esperto di Market Sentiment e News Analysis. Analizza le ultime notizie su {ticker_symbol}:
                            
                            ULTIME NOTIZIE:
                            {news_text}
                            
                            Fornisci un'analisi BREVE (max 200 parole) su:
                            1. Sentiment generale delle notizie (Positivo/Neutro/Negativo)
                            2. Impatto sulle prospettive dell'azienda
                            3. Fattori di rischio evidenti
                            4. Catalizzatori positivi o negativi
                            5. RATING SENTIMENT: Strong Buy / Buy / Hold / Sell (1 sola riga)
                            
                            Sii conciso e pratico, focalizzati sugli aspetti rilevanti per il trading a 2-4 settimane.
                            """
                            
                            try:
                                response = call_groq_api(prompt, max_tokens=400)
                                return response
                            except Exception as e:
                                return f"❌ Errore nell'analisi sentiment: {str(e)}"
                        
                        def generate_consensus_analysis(tech_analysis: str, fund_analysis: str, sentiment_analysis: str, ticker_symbol: str) -> str:
                            """
                            CONSENSO MULTI-AGENTE
                            I 3 agenti si confrontano e generano una raccomandazione finale
                            """
                            prompt = f"""
                            Sei il MODERATORE di un team di 3 analisti esperti che si confrontano su {ticker_symbol}.
                            
                            ANALISI TECNICA (Agente 1):
                            {tech_analysis}
                            
                            ANALISI FONDAMENTALE (Agente 2):
                            {fund_analysis}
                            
                            SENTIMENT NOTIZIE (Agente 3):
                            {sentiment_analysis}
                            
                            TASK:
                            1. Riassumi il consenso del team su {ticker_symbol}
                            2. Evidenzia dove gli agenti CONCORDANO e dove DISCORDANO
                            3. Identifica il fattore più critico
                            4. Valuta la coerenza tra i tre pareri
                            5. Genera RACCOMANDAZIONE FINALE: Strong Buy / Buy / Hold / Sell
                            6. Spiega il confidence level (0-100%)
                            7. Rischi principali e opportunità
                            
                            Formato CONCISO (max 300 parole). Usa tone professionale e dati-driven.
                            """
                            
                            try:
                                response = call_groq_api(prompt, max_tokens=600)
                                return response
                            except Exception as e:
                                return f"❌ Errore nel consenso multi-agente: {str(e)}"
                        
                        def display_multi_agent_analysis(ticker_ dict, signal: dict, ticker_symbol: str):
                            """
                            Visualizza l'analisi dei 3 agenti AI in Streamlit
                            """
                            st.markdown("---")
                            st.subheader("🤖 ANALISI MULTI-AGENTE AI (3 Analisti Esperti)")
                            st.markdown("*3 agenti esperti si confrontano per un'analisi completa*")
                            
                            col_info = st.container()
                            col_info.info("⏳ Generazione analisi AI in corso... (questo potrebbe richiedere 10-20 secondi)")
                            
                            placeholder_tech = st.empty()
                            placeholder_fund = st.empty()
                            placeholder_sentiment = st.empty()
                            
                            placeholder_tech.info("🔧 Agente Tecnico: Analisi in corso...")
                            tech_analysis = generate_technical_agent_analysis(signal, ticker_symbol)
                            placeholder_tech.empty()
                            
                            placeholder_fund.info("📊 Agente Fondamentale: Analisi in corso...")
                            fund_analysis = generate_fundamental_agent_analysis(ticker_data, ticker_symbol)
                            placeholder_fund.empty()
                            
                            placeholder_sentiment.info("📰 Agente News & Sentiment: Analisi in corso...")
                            sentiment_analysis = generate_news_sentiment_agent_analysis(ticker_data, ticker_symbol)
                            placeholder_sentiment.empty()
                            
                            tab_tech, tab_fund, tab_news, tab_consensus = st.tabs([
                                "🔧 Analista Tecnico",
                                "📊 Analista Fondamentale",
                                "📰 Sentiment & News",
                                "🎯 Consenso Finale"
                            ])
                            
                            with tab_tech:
                                st.markdown("### 🔧 ANALISTA TECNICO - Analisi ATR, RSI, Volatilità")
                                st.markdown(tech_analysis)
                            
                            with tab_fund:
                                st.markdown("### 📊 ANALISTA FONDAMENTALE - Analisi Bilanci, DCF, Crescita")
                                st.markdown(fund_analysis)
                            
                            with tab_news:
                                st.markdown("### 📰 ANALISTA SENTIMENT - News & Market Sentiment")
                                st.markdown(sentiment_analysis)
                            
                            with tab_consensus:
                                st.markdown("### 🎯 CONSENSO DEL TEAM - Raccomandazione Finale")
                                
                                st.info("⏳ Generazione consenso multi-agente...")
                                consensus = generate_consensus_analysis(tech_analysis, fund_analysis, sentiment_analysis, ticker_symbol)
                                
                                st.markdown(consensus)
                                
                                full_report = f"""
                        ╔════════════════════════════════════════════════════════════════╗
                        ║          REPORT COMPLETO MULTI-AGENTE AI - {ticker_symbol}         ║
                        ╚════════════════════════════════════════════════════════════════╝
                        
                        DATA ANALISI: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
                        
                        ────────────────────────────────────────────────────────────────
                        1️⃣ ANALISTA TECNICO
                        ────────────────────────────────────────────────────────────────
                        {tech_analysis}
                        
                        ────────────────────────────────────────────────────────────────
                        2️⃣ ANALISTA FONDAMENTALE
                        ────────────────────────────────────────────────────────────────
                        {fund_analysis}
                        
                        ────────────────────────────────────────────────────────────────
                        3️⃣ ANALISTA SENTIMENT & NEWS
                        ────────────────────────────────────────────────────────────────
                        {sentiment_analysis}
                        
                        ────────────────────────────────────────────────────────────────
                        🎯 CONSENSO MULTI-AGENTE (RACCOMANDAZIONE FINALE)
                        ────────────────────────────────────────────────────────────────
                        {consensus}
                        
                        ════════════════════════════════════════════════════════════════
                        Fine Report
                        ════════════════════════════════════════════════════════════════
                        """
                                
                                st.download_button(
                                    label="📥 Scarica Report Completo Multi-Agente",
                                    data=full_report,
                                    file_name=f"Multi_Agent_Report_{ticker_symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                                    mime="text/plain",
                                    use_container_width=True
                                )
                        
                        # ============================================================================
                        # CHIAMATA MULTI-AGENTE - INSERIRE DOPO LE NOTIZIE
                        # ============================================================================
                        
                        # AGGIUNGI QUESTA CHIAMATA SUBITO PRIMA DEL "DISCLAIMER":
                        if ticker_data and ticker_data['info'] and signal:
                            display_multi_agent_analysis(ticker_data, signal, ticker_input.upper())
                        
                        st.info("⚠️ Disclaimer: Questa analisi è solo a scopo educativo. Non è consulenza finanziaria.")
                    else:
                        st.error(f"❌ Impossibile recuperare dati per {ticker_input.upper()}")
            else:
                st.warning("⚠️ Inserisci un ticker valido")
        else:
            st.markdown("""
            ## 🚀 Benvenuto in Analisi Multi-Agente!
            Questa sezione ti consente di analizzare qualsiasi titolo con:
            - ✅ Stop Loss e Take Profit dinamici basati su volatilità (ATR)
            - ✅ Analisi tecnica avanzata
            - ✅ Ultime notizie
            👆 Inserisci un ticker nella barra di ricerca per iniziare!
            """)
