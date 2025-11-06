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
import feedparser
from urllib.parse import quote


# ============================================================================
# SEZIONE 1: FUNZIONI FORMATTAZIONE (TAB 1 e 2 - INVARIATE)
# ============================================================================

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
    """Format currency values - TAB 1 e 2"""
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
    """Format percentage values"""
    if pd.isna(value):
        return "N/A"
    return f"{value*100:.2f}%"

# ============================================================================
# SEZIONE 2: FUNZIONI TRADINGVIEW SCREENER (TAB 1 E 2 - INVARIATE)
# ============================================================================

def calculate_investment_score(df):
    """Calcola investment score"""
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
    """Genera URL TradingView"""
    if ':' in symbol:
        clean_symbol = symbol.split(':')[1]
    else:
        clean_symbol = symbol
    return f"https://www.tradingview.com/chart/?symbol={symbol}"

def fetch_screener_data():
    """Fetch dati da TradingView screener"""
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
    """Ottieni top 5 picks"""
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
# SEZIONE 3: FUNZIONI YFINANCE (TAB 3 - CON VALUTA CORRETTA)
# ============================================================================

def fetch_yfinance_data(ticker_symbol, period="1y"):
    """Fetch dati da yfinance + Google News RSS per notizie affidabili"""
    try:
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period=period)
        info = stock.info
        
        # Ottieni company name per le news
        company_name = info.get('longName', info.get('shortName', ticker_symbol))
        
        # USA GOOGLE NEWS RSS (sempre affidabile)
        news = fetch_google_news_rss(ticker_symbol, company_name)
        
        return {
            'history': hist, 
            'info': info, 
            'news': news, 
            'ticker': stock, 
            'symbol': ticker_symbol,
            'company_name': company_name
        }
    except Exception as e:
        st.error(f"❌ Errore nel caricamento dati: {e}")
        return None



def get_currency_symbol(ticker_data):
    """Ottieni simbolo valuta dal ticker"""
    info = ticker_data.get('info', {})
    currency_code = info.get('currency', 'USD')
    
    currency_map = {
        'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥', 
        'CHF': 'CHF', 'CAD': 'C$', 'AUD': 'A$', 'CNY': '¥',
        'INR': '₹', 'BRL': 'R$', 'RUB': '₽', 'KRW': '₩',
        'SEK': 'kr', 'NOK': 'kr', 'DKK': 'kr', 'PLN': 'zł',
        'TRY': '₺', 'ZAR': 'R', 'MXN': '$', 'SGD': 'S$',
        'HKD': 'HK$', 'NZD': 'NZ$', 'THB': '฿', 'PHP': '₱',
        'MYR': 'RM', 'IDR': 'Rp', 'VND': '₫', 'TWD': 'NT$'
    }
    return currency_map.get(currency_code, currency_code)

def fetch_google_news_rss(ticker_symbol, company_name=None):
    """
    Recupera notizie da Google News RSS feed
    Più affidabile di yfinance.get_news()
    """
    try:
        # Se non c'è company name, usa solo il ticker
        if not company_name or company_name == ticker_symbol:
            query = f"{ticker_symbol} stock"
        else:
            query = f"{company_name} {ticker_symbol} stock"
        
        # Encode query per URL
        encoded_query = quote(query)
        
        # Google News RSS URL
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        
        # Parse RSS feed
        feed = feedparser.parse(rss_url)
        
        news_list = []
        for entry in feed.entries[:10]:  # Max 10 notizie
            news_item = {
                'title': entry.get('title', 'N/A'),
                'link': entry.get('link', 'N/A'),
                'publisher': entry.get('source', {}).get('title', 'Google News'),
                'published': entry.get('published', 'N/A'),
                'summary': entry.get('summary', '')[:200]  # Prime 200 char
            }
            news_list.append(news_item)
        
        return news_list
    
    except Exception as e:
        print(f"⚠️ Errore Google News RSS: {e}")
        return []



# ============================================================================
# ANALISI TECNICA CORRETTA - CON INDICATORI CALCOLATI BENE
# ============================================================================

def calculate_sma(close, period):
    """Simple Moving Average"""
    try:
        return close.rolling(window=period).mean()
    except:
        return None

def calculate_ema(close, period):
    """Exponential Moving Average"""
    try:
        return close.ewm(span=period, adjust=False).mean()
    except:
        return None

def calculate_atr_corrected(high, low, close, period=14):
    """Average True Range - CORRETTO"""
    try:
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr
    except Exception as e:
        print(f"ATR Error: {e}")
        return None

def calculate_rsi_corrected(close, period=14):
    """RSI Corretto - Formula Standard"""
    try:
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    except Exception as e:
        print(f"RSI Error: {e}")
        return None

def calculate_macd_corrected(close, fast=12, slow=26, signal=9):
    """MACD Corretto"""
    try:
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    except Exception as e:
        print(f"MACD Error: {e}")
        return None, None, None

def calculate_bollinger_bands_corrected(close, period=20, num_std=2):
    """Bollinger Bands Corrette"""
    try:
        sma = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        upper_band = sma + (std * num_std)
        lower_band = sma - (std * num_std)
        bandwidth = ((upper_band - lower_band) / sma) * 100
        percent_b = (close - lower_band) / (upper_band - lower_band) * 100
        return upper_band, sma, lower_band, bandwidth, percent_b
    except Exception as e:
        print(f"BB Error: {e}")
        return None, None, None, None, None

def calculate_stochastic(high, low, close, k_period=14, d_period=3):
    """Stochastic Oscillator"""
    try:
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        k_percent = ((close - lowest_low) / (highest_high - lowest_low)) * 100
        d_percent = k_percent.rolling(window=d_period).mean()
        return k_percent, d_percent
    except Exception as e:
        print(f"Stochastic Error: {e}")
        return None, None

def calculate_dynamic_trading_signals_corrected(data, atr_multiplier_sl=2.0, atr_multiplier_tp=3.5):
    """
    ANALISI TECNICA COMPLETA E CORRETTA
    Con tutti gli indicatori calcolati bene
    """
    try:
        close = data['Close']
        high = data['High']
        low = data['Low']
        volume = data['Volume']

        # ===== CALCOLA TUTTI GLI INDICATORI =====

        # Moving Averages
        sma20 = calculate_sma(close, 20)
        sma50 = calculate_sma(close, 50)
        sma200 = calculate_sma(close, 200)
        ema12 = calculate_ema(close, 12)
        ema26 = calculate_ema(close, 26)

        # Volatilità
        atr = calculate_atr_corrected(high, low, close, 14)
        volatility = calculate_volatility(close, 20)

        # Momentum
        rsi = calculate_rsi_corrected(close, 14)
        macd_line, signal_line, histogram = calculate_macd_corrected(close, 12, 26, 9)

        # Bande e Support/Resistance
        bb_upper, bb_middle, bb_lower, bb_bandwidth, percent_b = calculate_bollinger_bands_corrected(close, 20, 2)

        # Stochastic
        k_stoch, d_stoch = calculate_stochastic(high, low, close, 14, 3)

        # ===== VALORI CORRENTI =====

        current_price = close.iloc[-1]
        latest_sma20 = sma20.iloc[-1] if sma20 is not None else current_price
        latest_sma50 = sma50.iloc[-1] if sma50 is not None else current_price
        latest_sma200 = sma200.iloc[-1] if sma200 is not None else current_price
        latest_rsi = rsi.iloc[-1] if rsi is not None else 50
        latest_macd = macd_line.iloc[-1] if macd_line is not None else 0
        latest_signal = signal_line.iloc[-1] if signal_line is not None else 0
        latest_histogram = histogram.iloc[-1] if histogram is not None else 0
        latest_atr = atr.iloc[-1] if atr is not None else current_price * 0.02
        latest_volatility = volatility.iloc[-1] if volatility is not None else 0.3
        latest_bb_upper = bb_upper.iloc[-1] if bb_upper is not None else current_price * 1.05
        latest_bb_lower = bb_lower.iloc[-1] if bb_lower is not None else current_price * 0.95
        latest_bb_middle = bb_middle.iloc[-1] if bb_middle is not None else current_price
        latest_bandwidth = bb_bandwidth.iloc[-1] if bb_bandwidth is not None else 10
        latest_percent_b = percent_b.iloc[-1] if percent_b is not None else 50
        latest_k_stoch = k_stoch.iloc[-1] if k_stoch is not None else 50
        latest_d_stoch = d_stoch.iloc[-1] if d_stoch is not None else 50

        support = latest_bb_lower
        resistance = latest_bb_upper

        avg_volume = volume.rolling(window=20).mean().iloc[-1]
        volume_ratio = volume.iloc[-1] / avg_volume if avg_volume > 0 else 1.0

        # ===== GENERA SEGNALE =====

        signal = {
            'direction': 'HOLD',
            'confidence': 0.0,
            'entry_point': current_price,
            'stop_loss': current_price,
            'take_profit': current_price,
            'risk_reward_ratio': 0.0,
            'atr_percent': (latest_atr / current_price) * 100,
            'sl_distance_percent': 0.0,
            'tp_distance_percent': 0.0,
            # Indicatori
            'rsi': latest_rsi,
            'macd_line': latest_macd,
            'macd_signal': latest_signal,
            'macd_histogram': latest_histogram,
            'atr': latest_atr,
            'volatility': latest_volatility * 100,
            'sma20': latest_sma20,
            'sma50': latest_sma50,
            'sma200': latest_sma200,
            'bb_upper': latest_bb_upper,
            'bb_middle': latest_bb_middle,
            'bb_lower': latest_bb_lower,
            'bb_bandwidth': latest_bandwidth,
            'percent_b': latest_percent_b,
            'stoch_k': latest_k_stoch,
            'stoch_d': latest_d_stoch,
            'support': support,
            'resistance': resistance,
            'volume_ratio': volume_ratio
        }

        # ===== LOGICA BUY/SELL =====

        buy_conditions = 0
        buy_confidence = 0.0

        # RSI oversold
        if latest_rsi < 30:
            buy_conditions += 1
            buy_confidence += 0.25
        elif latest_rsi < 40:
            buy_confidence += 0.10

        # Prezzo sotto lower BB
        if current_price <= latest_bb_lower * 1.02:
            buy_conditions += 1
            buy_confidence += 0.20

        # MACD positivo e crossover
        if latest_macd > latest_signal:
            buy_conditions += 1
            buy_confidence += 0.20
        if latest_histogram > 0 and latest_histogram < latest_histogram if len(histogram) > 1 else False:
            buy_confidence += 0.10

        # Volume alto
        if volume_ratio > 1.2:
            buy_conditions += 1
            buy_confidence += 0.15

        # Prezzo sopra SMA
        if current_price > latest_sma50 > latest_sma200:
            buy_confidence += 0.10

        # Stochastic oversold
        if latest_k_stoch < 20:
            buy_confidence += 0.10

        # Volatilità controllata
        if latest_volatility < 0.5:
            buy_confidence += 0.05

        # ===== SELL CONDITIONS =====

        sell_conditions = 0
        sell_confidence = 0.0

        # RSI overbought
        if latest_rsi > 70:
            sell_conditions += 1
            sell_confidence += 0.25
        elif latest_rsi > 60:
            sell_confidence += 0.10

        # Prezzo sopra upper BB
        if current_price >= latest_bb_upper * 0.98:
            sell_conditions += 1
            sell_confidence += 0.20

        # MACD negativo
        if latest_macd < latest_signal:
            sell_conditions += 1
            sell_confidence += 0.20

        # Volume alto
        if volume_ratio > 1.5:
            sell_conditions += 1
            sell_confidence += 0.15

        # Prezzo sotto SMA
        if current_price < latest_sma50:
            sell_confidence += 0.10

        # Stochastic overbought
        if latest_k_stoch > 80:
            sell_confidence += 0.10

        # ===== DETERMINA DIREZIONE =====

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

        # ===== RISK/REWARD =====

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
        signal['sl_distance_percent'] = (abs(signal['entry_point'] - signal['stop_loss']) / signal['entry_point']) * 100
        signal['tp_distance_percent'] = (abs(signal['take_profit'] - signal['entry_point']) / signal['entry_point']) * 100

        return signal

    except Exception as e:
        st.error(f"Errore nel calcolo dei segnali tecnici: {e}")
        import traceback
        traceback.print_exc()
        return None

# ============================================================================
# ANALISI FONDAMENTALE CORRETTA - CON DCF COMPLETO
# ============================================================================

def calculate_dcf_valuation(ticker_data):
    """
    DCF VALUATION COMPLETO
    Segue il metodo standard:
    1. Stima FCF futuri
    2. Determina WACC (tasso di sconto)
    3. Attualizza i FCF
    4. Calcola Terminal Value
    5. Somma per ottenere Enterprise Value
    """

    try:
        info = ticker_data['info']
        cashflow = ticker_data.get('cashflow', pd.DataFrame())

        # ===== 1. ESTRAI DATI STORICI =====

        fcf_history = []
        if len(cashflow) > 0:
            # Free Cash Flow è di solito alla riga 2 (OCF - CapEx)
            try:
                ocf_values = cashflow.iloc[0].values[:5]  # Ultimi 5 anni
                capex_values = cashflow.iloc[1].values[:5]

                for ocf, capex in zip(ocf_values, capex_values):
                    if pd.notna(ocf) and pd.notna(capex):
                        fcf = ocf + capex  # CapEx è negativo, quindi si somma
                        fcf_history.append(fcf)
            except:
                pass

        if not fcf_history:
            # Fallback: usa FCF da info
            fcf_latest = info.get('freeCashflow', 0)
            if fcf_latest:
                fcf_history = [fcf_latest]

        if not fcf_history or fcf_history[0] == 0:
            return None

        # ===== 2. CALCOLA WACC (TASSO DI SCONTO) =====

        risk_free_rate = 0.045  # 4.5%
        market_risk_premium = 0.065  # 6.5%
        beta = info.get('beta', 1.0) or 1.0

        # Cost of Equity (CAPM)
        cost_of_equity = risk_free_rate + beta * market_risk_premium

        # Market cap e Debt
        market_cap = info.get('marketCap', 1)
        total_debt = info.get('totalDebt', 0)
        total_cash = info.get('totalCash', 0)

        # Cost of Debt
        try:
            income = ticker_data.get('income_stmt', pd.DataFrame())
            if len(income) > 0:
                interest_exp = income.iloc[0].get('Interest Expense', 0) if 'Interest Expense' in income.index else 0
                cost_of_debt = abs(interest_exp) / max(total_debt, 1) if total_debt > 0 else 0.05
            else:
                cost_of_debt = 0.05
        except:
            cost_of_debt = 0.05

        # Tax Rate
        try:
            if len(income) > 0:
                tax_exp = income.iloc[0].get('Income Tax Expense', 0) if 'Income Tax Expense' in income.index else 0
                net_income = income.iloc[0].get('Net Income', 0) if 'Net Income' in income.index else 0
                pretax_income = net_income + tax_exp
                tax_rate = abs(tax_exp) / max(pretax_income, 1) if pretax_income > 0 else 0.2
            else:
                tax_rate = 0.2
        except:
            tax_rate = 0.2

        # WACC Formula
        total_value = market_cap + total_debt
        wacc = (market_cap / total_value * cost_of_equity) + (total_debt / total_value * cost_of_debt * (1 - tax_rate))
        wacc = max(wacc, 0.05)  # Min 5%

        # ===== 3. STIMA FCF FUTURI (5 ANNI) =====

        base_fcf = fcf_history[0]

        # Calcola tasso di crescita storico
        if len(fcf_history) > 1:
            valid_fcf = [f for f in fcf_history if f > 0]
            if len(valid_fcf) > 1:
                growth_rate = (valid_fcf[-1] / valid_fcf[0]) ** (1 / (len(valid_fcf) - 1)) - 1
            else:
                growth_rate = 0.05  # Default 5%
        else:
            growth_rate = 0.05

        # Limita growth rate
        growth_rate = max(min(growth_rate, 0.20), -0.10)  # Tra -10% e +20%

        # Proietta FCF 5 anni
        projected_fcf = []
        for year in range(1, 6):
            fcf_proj = base_fcf * ((1 + growth_rate) ** year)
            projected_fcf.append(fcf_proj)

        # ===== 4. CALCOLA TERMINAL VALUE =====

        terminal_growth = 0.025  # 2.5%
        terminal_fcf = projected_fcf[-1] * (1 + terminal_growth)

        if wacc > terminal_growth:
            terminal_value = terminal_fcf / (wacc - terminal_growth)
        else:
            terminal_value = terminal_fcf / 0.05

        # ===== 5. ATTUALIZZA AL PRESENTE =====

        pv_fcf_list = []
        for year, fcf in enumerate(projected_fcf, 1):
            pv = fcf / ((1 + wacc) ** year)
            pv_fcf_list.append(pv)

        pv_fcf_total = sum(pv_fcf_list)
        pv_terminal_value = terminal_value / ((1 + wacc) ** 5)

        # ===== 6. CALCOLA ENTERPRISE E EQUITY VALUE =====

        enterprise_value = pv_fcf_total + pv_terminal_value
        net_debt = total_debt - total_cash
        equity_value = enterprise_value - net_debt

        shares_out = info.get('sharesOutstanding', 1)
        intrinsic_value = equity_value / shares_out

        current_price = info.get('currentPrice', 1)
        upside_downside = ((intrinsic_value / current_price) - 1) * 100

        return {
            'intrinsic_value': intrinsic_value,
            'current_price': current_price,
            'upside_downside': upside_downside,
            'enterprise_value': enterprise_value,
            'equity_value': equity_value,
            'terminal_value': terminal_value,
            'pv_fcf_total': pv_fcf_total,
            'pv_terminal': pv_terminal_value,
            'wacc': wacc,
            'cost_of_equity': cost_of_equity,
            'cost_of_debt': cost_of_debt,
            'tax_rate': tax_rate,
            'base_fcf': base_fcf,
            'growth_rate': growth_rate,
            'projected_fcf': projected_fcf,
            'terminal_fcf': terminal_fcf,
            'recommendation': 'STRONG BUY' if upside_downside > 30 else 'BUY' if upside_downside > 15 else 'HOLD' if upside_downside > -15 else 'SELL'
        }

    except Exception as e:
        print(f"DCF Error: {e}")
        import traceback
        traceback.print_exc()
        return None

# ============================================================================
# SEZIONE 4: FUNZIONI AGENTI AI MULTI-AGENTE (TAB 3)
# ============================================================================

def generate_technical_agent_analysis(signal: dict, ticker_symbol: str) -> str:
    """AGENTE 1: ANALISTA TECNICO"""
    prompt = f"""
    Sei un esperto di Analisi Tecnica. Analizza il seguente titolo {ticker_symbol}:
    
    DATI TECNICI:
    - Segnale: {signal['direction']}
    - Confidenza: {signal['confidence']*100:.0f}%
    - Prezzo: {signal['entry_point']:.2f}
    - RSI: {signal['rsi']:.1f}
    - MACD: {signal['macd']:.4f}
    - ATR (Volatilità): {signal['atr']:.2f} ({signal['atr_percent']:.2f}%)
    - Volatilità Annualizzata: {signal['volatility']:.1f}%
    - Support: {signal['support']:.2f}
    - Resistance: {signal['resistance']:.2f}
    - Volume Ratio: {signal['volume_ratio']:.2f}x
    - Risk/Reward: 1:{signal['risk_reward_ratio']:.2f}
    
    LIVELLI DI TRADING (Basati su ATR):
    - Entry: {signal['entry_point']:.2f}
    - Stop Loss: {signal['stop_loss']:.2f} (-{signal['sl_distance_percent']:.2f}%)
    - Take Profit: {signal['take_profit']:.2f} (+{signal['tp_distance_percent']:.2f}%)
    
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

# Calcola DCF PRIMA di fare l'analisi
dcf = calculate_dcf_valuation(ticker_data)


def generate_fundamental_agent_analysis(ticker_ dict, ticker_symbol: str) -> str:
    """AGENTE 2: ANALISTA FONDAMENTALE - CON DCF"""
    info = ticker_data['info']
    
    # Parametri base
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
    
    # ===== CALCOLA DCF (NUOVA SEZIONE) =====
    dcf = calculate_dcf_valuation(ticker_data)
    
    # ===== COSTRUISCI IL PROMPT CON DCF =====
    
    # Se DCF disponibile, aggiungi al prompt
    if dcf:
        dcf_section = f"""
    
    📊 DCF VALUATION (Discounted Cash Flow):
    - Intrinsic Value per Share: ${dcf['intrinsic_value']:.2f}
    - Current Market Price: ${dcf['current_price']:.2f}
    - Upside/Downside: {dcf['upside_downside']:.1f}%
    - Raccomandazione DCF: {dcf['recommendation']}
    
    📈 WACC & DISCOUNT RATE:
    - WACC (Weighted Average Cost of Capital): {dcf['wacc']*100:.2f}%
    - Cost of Equity (CAPM): {dcf['cost_of_equity']*100:.2f}%
    - Cost of Debt: {dcf['cost_of_debt']*100:.2f}%
    - Tax Rate: {dcf['tax_rate']*100:.2f}%
    
    💰 FREE CASH FLOW ANALYSIS:
    - Base FCF (storico): ${dcf['base_fcf']/1e9:.2f}B
    - Growth Rate stimato: {dcf['growth_rate']*100:.2f}%
    - FCF Projection (5 anni):
      • Anno 1: ${dcf['projected_fcf'][0]/1e9:.2f}B
      • Anno 2: ${dcf['projected_fcf'][1]/1e9:.2f}B
      • Anno 3: ${dcf['projected_fcf'][2]/1e9:.2f}B
      • Anno 4: ${dcf['projected_fcf'][3]/1e9:.2f}B
      • Anno 5: ${dcf['projected_fcf'][4]/1e9:.2f}B
    
    🎯 ENTERPRISE & EQUITY VALUE:
    - Enterprise Value: ${dcf['enterprise_value']/1e9:.2f}B
    - PV dei FCF (5 anni): ${dcf['pv_fcf_total']/1e9:.2f}B
    - Terminal Value: ${dcf['terminal_value']/1e9:.2f}B
    - PV Terminal Value: ${dcf['pv_terminal']/1e9:.2f}B
    - Equity Value: ${dcf['equity_value']/1e9:.2f}B
        """
    else:
        dcf_section = """
    
    📊 DCF VALUATION:
    ⚠️ Dati insufficienti per calcolare il DCF per questo ticker.
        """
    
    # Prompt completo
    prompt = f"""
    Sei un esperto di Analisi Fondamentale. Analizza il titolo {ticker_symbol}:
    
    METRICHE DI VALUTAZIONE TRADIZIONALI:
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
    {dcf_section}
    
    Fornisci un'analisi BREVE (max 250 parole) su:
    1. Valutazione dell'azione secondo DCF vs multipli tradizionali
    2. Il DCF suggerisce sottovalutazione o sopravvalutazione?
    3. Qualità e sostenibilità dei FCF proiettati
    4. WACC appropriato per il livello di rischio?
    5. Confronto Intrinsic Value DCF vs Current Price
    6. RATING FONDAMENTALE: Strong Buy / Buy / Hold / Sell (1 sola riga finale)
    
    Concentrati sull'analisi DCF se disponibile, altrimenti usa i multipli tradizionali.
    """
    
    try:
        response = call_groq_api(prompt, max_tokens=500)
        return response
    except Exception as e:
        return f"❌ Errore nell'analisi fondamentale: {str(e)}"

def generate_news_sentiment_agent_analysis(ticker_data: dict, ticker_symbol: str) -> str:
    """AGENTE 3: ANALISTA NEWS & SENTIMENT"""
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
    """CONSENSO MULTI-AGENTE"""
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
    """Visualizza analisi dei 3 agenti AI"""
    st.markdown("---")
    st.subheader("🤖 ANALISI MULTI-AGENTE AI (3 Analisti Esperti)")
    st.markdown("*3 agenti esperti si confrontano per un'analisi completa*")
    
    # ===== CALCOLA DCF UNA VOLTA SOLA (PRIMA DI CHIAMARE GLI AGENTI) =====
    dcf = calculate_dcf_valuation(ticker_data)
    
    # Info placeholder
    col_info = st.container()
    col_info.info("⏳ Generazione analisi AI in corso... (questo potrebbe richiedere 10-20 secondi)")
    
    placeholder_tech = st.empty()
    placeholder_fund = st.empty()
    placeholder_sentiment = st.empty()
    
    # Genera Analisi Tecnica
    placeholder_tech.info("🔧 Agente Tecnico: Analisi in corso...")
    tech_analysis = generate_technical_agent_analysis(signal, ticker_symbol)
    placeholder_tech.empty()
    
    # Genera Analisi Fondamentale (ORA CON DCF)
    placeholder_fund.info("📊 Agente Fondamentale: Analisi in corso...")
    fund_analysis = generate_fundamental_agent_analysis(ticker_data, ticker_symbol)
    placeholder_fund.empty()
    
    # Genera Analisi Sentiment
    placeholder_sentiment.info("📰 Agente News & Sentiment: Analisi in corso...")
    sentiment_analysis = generate_news_sentiment_agent_analysis(ticker_data, ticker_symbol)
    placeholder_sentiment.empty()
    
    # Display TAB
    tab_tech, tab_fund, tab_news, tab_consensus = st.tabs([
        "🔧 Analista Tecnico",
        "📊 Analista Fondamentale",
        "📰 Sentiment & News",
        "🎯 Consenso Finale"
    ])
    
    with tab_tech:
        st.markdown("### 🔧 ANALISTA TECNICO")
        st.markdown(tech_analysis)
    
    with tab_fund:
        st.markdown("### 📊 ANALISTA FONDAMENTALE - DCF Analysis")
        
        # ===== MOSTRA DCF PRIMA DELL'ANALISI AI =====
        if dcf:
            st.markdown("#### 💎 DCF VALUATION RESULTS")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Intrinsic Value", f"${dcf['intrinsic_value']:.2f}")
            with col2:
                st.metric("Current Price", f"${dcf['current_price']:.2f}")
            with col3:
                color = "🟢" if dcf['upside_downside'] > 0 else "🔴"
                st.metric("Upside/Downside", f"{color} {dcf['upside_downside']:.1f}%")
            
            st.markdown(f"**DCF Recommendation:** {dcf['recommendation']}")
            
            with st.expander("📊 DCF Details"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"""
                    **WACC Calculation:**
                    - WACC: {dcf['wacc']*100:.2f}%
                    - Cost of Equity: {dcf['cost_of_equity']*100:.2f}%
                    - Cost of Debt: {dcf['cost_of_debt']*100:.2f}%
                    - Tax Rate: {dcf['tax_rate']*100:.2f}%
                    """)
                with col2:
                    st.markdown(f"""
                    **Enterprise Value:**
                    - EV: ${dcf['enterprise_value']/1e9:.2f}B
                    - PV FCF: ${dcf['pv_fcf_total']/1e9:.2f}B
                    - Terminal Value: ${dcf['terminal_value']/1e9:.2f}B
                    - Equity Value: ${dcf['equity_value']/1e9:.2f}B
                    """)
        
        st.markdown("---")
        st.markdown("### 🤖 AI Analysis")
        st.markdown(fund_analysis)
    
    with tab_news:
        st.markdown("### 📰 ANALISTA SENTIMENT")
        st.markdown(sentiment_analysis)
    
    with tab_consensus:
        st.markdown("### 🎯 CONSENSO DEL TEAM")
        
        st.info("⏳ Generazione consenso multi-agente...")
        consensus = generate_consensus_analysis(tech_analysis, fund_analysis, sentiment_analysis, ticker_symbol)
        
        st.markdown(consensus)
        
        # Download report
        full_report = f"""
╔════════════════════════════════════════════════════════════════╗
║          REPORT COMPLETO MULTI-AGENTE AI - {ticker_symbol}         ║
╚════════════════════════════════════════════════════════════════╝

DATA ANALISI: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

────────────────────────────────────────────────────────────────
DCF VALUATION SUMMARY
────────────────────────────────────────────────────────────────
{f'''
Intrinsic Value: ${dcf['intrinsic_value']:.2f}
Current Price: ${dcf['current_price']:.2f}
Upside/Downside: {dcf['upside_downside']:.1f}%
WACC: {dcf['wacc']*100:.2f}%
Recommendation: {dcf['recommendation']}
''' if dcf else 'DCF non disponibile'}

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
# SEZIONE 5: MAIN FUNCTION stock_screener_app()
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
    
    # ========== TAB 3: YFINANCE ANALYSIS CON VALUTA CORRETTA ==========
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
                        symbol = get_currency_symbol(ticker_data)
                        
                        # Metriche generali CON VALUTA
                        st.markdown("---")
                        st.subheader("📈 Informazioni Generali")
                        
                        col1, col2, col3, col4, col5 = st.columns(5)
                        with col1:
                            st.metric("💰 Prezzo Attuale", f"{symbol}{current_price:.2f}")
                        with col2:
                            market_cap = info.get('marketCap')
                            if market_cap and market_cap >= 1e9:
                                st.metric("🏦 Market Cap", f"{symbol}{market_cap/1e9:.2f}B")
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
                            atr_sl = st.slider("ATR Multiplier SL", min_value=1.0, max_value=4.0, value=2.0, step=0.5)
                        with col2:
                            atr_tp = st.slider("ATR Multiplier TP", min_value=1.5, max_value=6.0, value=3.5, step=0.5)
                        with col3:
                            period_selection = st.selectbox("Periodo Analisi", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=2)
                        
                        signal = calculate_dynamic_trading_signals(ticker_data['history'], atr_multiplier_sl=atr_sl, atr_multiplier_tp=atr_tp)
                        
                        if signal:
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                color_emoji = "🟢" if signal['direction'] == "BUY" else "🔴" if signal['direction'] == "SELL" else "🟡"
                                st.metric(f"{color_emoji} Segnale Finale", signal['direction'], f"{signal['confidence']*100:.0f}% confidence")
                            with col2:
                                st.metric("📊 ATR (Volatilità)", f"{symbol}{signal['atr']:.2f}", f"{signal['atr_percent']:.2f}% del prezzo")
                            with col3:
                                st.metric("📈 Volatilità Storica", f"{signal['volatility']:.1f}%", "Annualizzata")
                            with col4:
                                rr_status = "✅ Ottimo" if signal['risk_reward_ratio'] >= 2.0 else "⚠️ Accettabile"
                                st.metric("Risk/Reward", f"1:{signal['risk_reward_ratio']:.2f}", rr_status)
                            
                            st.markdown("### 📍 Livelli di Trading (Basati su ATR)")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.markdown(f"**Entry Point:**")
                                st.markdown(f"# `{symbol}{signal['entry_point']:.2f}`")
                            with col2:
                                st.markdown(f"**Stop Loss (SL):**")
                                st.markdown(f"# `{symbol}{signal['stop_loss']:.2f}`")
                                st.caption(f"📉 -{signal['sl_distance_percent']:.2f}%")
                            with col3:
                                st.markdown(f"**Take Profit (TP):**")
                                st.markdown(f"# `{symbol}{signal['take_profit']:.2f}`")
                                st.caption(f"📈 +{signal['tp_distance_percent']:.2f}%")
                        else:
                            st.error("❌ Errore nel calcolo dei segnali")
                        
                        # Notizie
                        # Notizie - GOOGLE NEWS RSS
                        st.markdown("---")
                        st.subheader("📰 Ultime Notizie (Google News)")
                        
                        if ticker_data and ticker_data.get('news'):
                            news_list = ticker_data['news']
                            
                            if len(news_list) > 0:
                                st.info(f"📰 {len(news_list)} notizie trovate per {ticker_input.upper()}")
                                
                                # Mostra max 5 notizie
                                for i, news_item in enumerate(news_list[:5], 1):
                                    with st.expander(f"📰 Notizia {i}: {news_item.get('title', 'N/A')[:60]}..."):
                                        col1, col2 = st.columns([3, 1])
                                        
                                        with col1:
                                            st.markdown(f"**Titolo:** {news_item.get('title', 'N/A')}")
                                            st.markdown(f"**Publisher:** {news_item.get('publisher', 'N/A')}")
                                            st.markdown(f"**Pubblicato:** {news_item.get('published', 'N/A')}")
                                            
                                            # Summary se disponibile
                                            summary = news_item.get('summary', '')
                                            if summary:
                                                st.caption(f"{summary}...")
                                        
                                        with col2:
                                            link = news_item.get('link', '#')
                                            st.link_button("📖 Leggi", link, use_container_width=True)
                            else:
                                st.warning(f"⚠️ Nessuna notizia trovata per {ticker_input.upper()}")
                        else:
                            st.info("ℹ️ Nessuna notizia disponibile")

                        
                        # MULTI-AGENT AI ANALYSIS
                        if ticker_data and ticker_data['info'] and signal:
                            display_multi_agent_analysis(ticker_data, signal, ticker_input.upper())
                        else:
                            st.warning("⚠️ Impossibile generare analisi multi-agente: dati insufficienti")
                        
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
            - ✅ Analisi fondamentale completa
            - ✅ Sentiment & News Analysis
            - ✅ 3 Agenti AI che si confrontano
            👆 Inserisci un ticker nella barra di ricerca per iniziare!
            """)

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    stock_screener_app()
