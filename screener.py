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

# ================= FUNZIONI FORMATTAZIONE ===================
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

# ================= FUNZIONI YFINANCE & INDICATORI ==============
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

# ================== CODICE TAB 3 ===================

def tab3_yfinance_analysis():
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
    quick_tickers = [
        ("🍎 AAPL", "AAPL"),
        ("🚗 TSLA", "TSLA"),
        ("🤖 MSFT", "MSFT"),
        ("💎 BRK.A", "BRK.A"),
        ("📱 META", "META")
    ]
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
                        st.metric("💰 Prezzo Attuale", f"${current_price:.2f}")
                    with col2:
                        market_cap = info.get('marketCap')
                        if market_cap and market_cap >= 1e9:
                            st.metric("🏦 Market Cap", f"${market_cap/1e9:.2f}B")
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
                        atr_sl = st.slider(
                            "ATR Multiplier SL",
                            min_value=1.0,
                            max_value=4.0,
                            value=2.0,
                            step=0.5,
                            help="Quanti ATR per Stop Loss"
                        )
                    with col2:
                        atr_tp = st.slider(
                            "ATR Multiplier TP",
                            min_value=1.5,
                            max_value=6.0,
                            value=3.5,
                            step=0.5,
                            help="Quanti ATR per Take Profit"
                        )
                    with col3:
                        period_selection = st.selectbox(
                            "Periodo Analisi",
                            ["1mo", "3mo", "6mo", "1y", "2y", "5y"],
                            index=2
                        )
                    
                    signal = calculate_dynamic_trading_signals(
                        ticker_data['history'],
                        atr_multiplier_sl=atr_sl,
                        atr_multiplier_tp=atr_tp
                    )
                    if signal:
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            color_emoji = "🟢" if signal['direction'] == "BUY" else "🔴" if signal['direction'] == "SELL" else "🟡"
                            st.metric(
                                f"{color_emoji} Segnale Finale",
                                signal['direction'],
                                f"{signal['confidence']*100:.0f}% confidence"
                            )
                        with col2:
                            st.metric(
                                "📊 ATR (Volatilità)",
                                f"${signal['atr']:.2f}",
                                f"{signal['atr_percent']:.2f}% del prezzo"
                            )
                        with col3:
                            st.metric(
                                "📈 Volatilità Storica",
                                f"{signal['volatility']:.1f}%",
                                "Annualizzata"
                            )
                        with col4:
                            rr_status = "✅ Ottimo" if signal['risk_reward_ratio'] >= 2.0 else "⚠️ Accettabile"
                            st.metric("Risk/Reward", f"1:{signal['risk_reward_ratio']:.2f}", rr_status)
                        
                        st.markdown("### 📍 Livelli di Trading (Basati su ATR)")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.markdown(f"**Entry Point:**")
                            st.markdown(f"# `${signal['entry_point']:.2f}`")
                        with col2:
                            st.markdown(f"**Stop Loss (SL):**")
                            st.markdown(f"# `${signal['stop_loss']:.2f}`")
                            st.caption(f"📉 -{signal['sl_distance_percent']:.2f}%")
                        with col3:
                            st.markdown(f"**Take Profit (TP):**")
                            st.markdown(f"# `${signal['take_profit']:.2f}`")
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
                    
                    st.info(
                        "⚠️ Disclaimer: Questa analisi è solo a scopo educativo. "
                        "Non è consulenza finanziaria. SL/TP sono calcolati automaticamente basati su volatilità"
                    )
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
        - ✅ Esportazione dati
        👆 Inserisci un ticker nella barra di ricerca per iniziare!
        """)

def main():
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard TradingView", "🎯 Top Picks", "🔍 Analisi yfinance"])

    with tab1:
        st.subheader("Dashboard TradingView Screener")
        st.info("📊 Aggiorna clicca 'Aggiorna Dati' per caricare il screener da TradingView")
        # Codice originale per tab1 come nel tuo file

    with tab2:
        st.subheader("Top 5 Investment Picks")
        st.info("🎯 I top 5 ticker verranno mostrati qui dopo l'aggiornamento dei dati")
        # Codice originale per tab2 come nel tuo file

    with tab3:
        tab3_yfinance_analysis()

if __name__ == "__main__":
    main()
