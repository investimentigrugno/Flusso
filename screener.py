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
# FUNZIONI DI FORMATTAZIONE E CALCOLO
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
    """Format currency values"""
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
    return f"{value:.2f}%"

# ============================================================================
# FUNZIONI FETCH E CALCOLO ATR/VOLATILITÀ
# ============================================================================

def fetch_yfinance_data(ticker_symbol, period="1y"):
    """Fetch dati completi da yfinance"""
    try:
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period=period)
        info = stock.info
        news = stock.news[:5] if hasattr(stock, 'news') else []

        return {
            'history': hist,
            'info': info,
            'news': news,
            'ticker': stock,
            'symbol': ticker_symbol
        }
    except Exception as e:
        st.error(f"❌ Errore nel caricamento dati: {e}")
        return None

def calculate_atr(high, low, close, period=14):
    """Average True Range - Misura volatilità"""
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
    """Volatilità storica annualizzata"""
    try:
        returns = close.pct_change()
        volatility = returns.rolling(window=period).std() * np.sqrt(252)
        return volatility
    except:
        return None

def calculate_bollinger_bands(close, period=20, num_std=2):
    """Bollinger Bands per supporto/resistenza dinamici"""
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
    """Relative Strength Index"""
    try:
        return ta.momentum.rsi(close, length=period)
    except:
        return None

def calculate_macd_diff(close, fast=12, slow=26):
    """MACD differenza"""
    try:
        return ta.trend.macd_diff(close, fast=fast, slow=slow)
    except:
        return None

def calculate_dynamic_trading_signals(data, atr_multiplier_sl=2.0, atr_multiplier_tp=3.5):
    """
    Calcola Entry/SL/TP dinamici basati su volatilità (ATR)
    """
    try:
        close = data['Close']
        high = data['High']
        low = data['Low']
        volume = data['Volume']

        # Indicatori tecnici
        rsi = calculate_rsi(close)
        macd = calculate_macd_diff(close)

        # Volatilità e ATR
        atr = calculate_atr(high, low, close, period=14)
        volatility = calculate_volatility(close, period=20)

        # Bollinger Bands
        bb_upper, bb_middle, bb_lower, bb_bandwidth = calculate_bollinger_bands(close)

        # Valori attuali
        current_price = close.iloc[-1]
        latest_rsi = rsi.iloc[-1] if rsi is not None else 50
        latest_macd = macd.iloc[-1] if macd is not None else 0
        latest_atr = atr.iloc[-1] if atr is not None else current_price * 0.02
        latest_volatility = volatility.iloc[-1] if volatility is not None else 0.3
        latest_bb_upper = bb_upper.iloc[-1] if bb_upper is not None else current_price * 1.05
        latest_bb_lower = bb_lower.iloc[-1] if bb_lower is not None else current_price * 0.95
        latest_bb_middle = bb_middle.iloc[-1] if bb_middle is not None else current_price
        latest_bandwidth = bb_bandwidth.iloc[-1] if bb_bandwidth is not None else 0.1

        # Supporto e Resistenza dinamici
        support = latest_bb_lower
        resistance = latest_bb_upper

        # Volume analysis
        avg_volume = volume.rolling(window=20).mean().iloc[-1]
        volume_ratio = volume.iloc[-1] / avg_volume if avg_volume > 0 else 1.0

        # Inizializza signal
        signal = {
            'direction': 'HOLD',
            'confidence': 0.0,
            'entry_point': current_price,
            'stop_loss': current_price,
            'take_profit': current_price,
            'rsi': latest_rsi,
            'macd': latest_macd,
            'atr': latest_atr,
            'volatility': latest_volatility * 100 if latest_volatility else 0,
            'support': support,
            'resistance': resistance,
            'bb_bandwidth': latest_bandwidth * 100 if latest_bandwidth else 0,
            'volume_ratio': volume_ratio,
            'risk_reward_ratio': 0.0
        }

        # LOGICA DECISIONALE
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

        # Condizioni SELL
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

        # CALCOLO ENTRY/SL/TP BASATI SU ATR

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

        # Risk/Reward
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

        # Percentuali
        signal['atr_percent'] = (latest_atr / current_price) * 100
        signal['sl_distance_percent'] = (abs(signal['entry_point'] - signal['stop_loss']) / signal['entry_point']) * 100
        signal['tp_distance_percent'] = (abs(signal['take_profit'] - signal['entry_point']) / signal['entry_point']) * 100

        return signal

    except Exception as e:
        st.error(f"Errore nel calcolo dei segnali: {e}")
        return None

# ============================================================================
# FUNZIONI DCF E WACC
# ============================================================================

def calculate_wacc(data, risk_free_rate=0.045, market_risk_premium=0.065):
    """Calcola WACC per DCF"""
    try:
        info = data.get('info', {})
        income = data.get('income_stmt', pd.DataFrame())

        beta = info.get('beta', 1.0) or 1.0
        cost_of_equity = risk_free_rate + beta * market_risk_premium
        market_cap = info.get('marketCap', 1) or 1
        total_debt = info.get('totalDebt', 0) or 0

        try:
            if len(income) > 0 and 'Interest Expense' in income.index:
                interest_expense = float(income.iloc[0]['Interest Expense']) or 0
            else:
                interest_expense = 0
        except:
            interest_expense = 0

        cost_of_debt = (interest_expense / max(total_debt, 1) if total_debt > 0 else 0.05) or 0.05

        try:
            if len(income) > 0 and 'Income Tax Expense' in income.index:
                tax_expense = float(income.iloc[0]['Income Tax Expense']) or 0
            else:
                tax_expense = 0

            if len(income) > 0 and 'Net Income' in income.index:
                net_income = float(income.iloc[0]['Net Income']) or 0
            else:
                net_income = 0
        except:
            tax_expense = 0
            net_income = 0

        total_income_before_tax = interest_expense + (net_income + tax_expense) or 1
        tax_rate = (tax_expense / max(total_income_before_tax, 1) if total_income_before_tax > 0 else 0.2) or 0.2

        total_value = market_cap + total_debt or 1

        if total_value > 0:
            wacc = (market_cap / total_value * cost_of_equity) + (total_debt / total_value * cost_of_debt * (1 - tax_rate))
            return max(wacc, 0.05), cost_of_equity, cost_of_debt, tax_rate
        else:
            return cost_of_equity, cost_of_equity, 0.05, tax_rate

    except Exception as e:
        return 0.10, 0.10, 0.05, 0.2

def analyze_cash_flows(data):
    """Analizza FCF storici"""
    try:
        cashflow = data.get('cashflow', pd.DataFrame())

        if len(cashflow.columns) == 0:
            return None

        periods = min(5, len(cashflow.columns))
        ocf_list = []
        fcf_list = []
        capex_list = []

        for i in range(periods):
            try:
                ocf = float(cashflow.iloc[0, i]) if len(cashflow) > 0 else 0
                capex = float(cashflow.iloc[1, i]) if len(cashflow) > 1 else 0
                fcf = ocf + capex

                ocf_list.append(ocf)
                capex_list.append(capex)
                fcf_list.append(fcf)
            except:
                pass

        if len(fcf_list) > 1:
            fcf_valid = [x for x in fcf_list if x != 0]
            if len(fcf_valid) > 1:
                fcf_growth = (fcf_valid[-1] / fcf_valid[0]) ** (1 / (len(fcf_valid) - 1)) - 1
            else:
                fcf_growth = 0
        else:
            fcf_growth = 0

        return {
            'ocf_list': ocf_list,
            'fcf_list': fcf_list,
            'capex_list': capex_list,
            'avg_fcf': np.mean([x for x in fcf_list if x != 0]) if fcf_list else 0,
            'avg_ocf': np.mean([x for x in ocf_list if x != 0]) if ocf_list else 0,
            'avg_capex': np.mean([abs(x) for x in capex_list if x != 0]) if capex_list else 0,
            'fcf_growth': fcf_growth,
            'periods': periods
        }
    except:
        return None

def calculate_dcf(data, wacc, forecast_years=5, terminal_growth=0.025):
    """Valutazione DCF"""
    try:
        info = data.get('info', {})
        cf_analysis = analyze_cash_flows(data)

        if not cf_analysis or cf_analysis.get('avg_fcf', 0) == 0:
            return None

        base_fcf = cf_analysis['avg_fcf'] or 1
        fcf_growth = cf_analysis.get('fcf_growth', 0) or 0

        # Proietta FCF
        projected_fcf = []
        for year in range(1, forecast_years + 1):
            fcf = base_fcf * ((1 + fcf_growth) ** year)
            projected_fcf.append(fcf)

        # Terminal Value
        if wacc > terminal_growth:
            terminal_fcf = projected_fcf[-1] * (1 + terminal_growth)
            terminal_value = terminal_fcf / (wacc - terminal_growth)
        else:
            terminal_value = 0

        # Sconta al presente
        pv_fcf = sum([fcf / ((1 + wacc) ** (i+1)) for i, fcf in enumerate(projected_fcf)])
        pv_terminal = terminal_value / ((1 + wacc) ** forecast_years) if terminal_value > 0 else 0

        # Enterprise Value
        enterprise_value = pv_fcf + pv_terminal

        # Equity Value
        net_debt = (info.get('totalDebt', 0) or 0) - (info.get('totalCash', 0) or 0)
        equity_value = enterprise_value - net_debt

        # Value per share
        shares = info.get('sharesOutstanding', 1) or 1
        value_per_share = equity_value / max(shares, 1)

        current_price = info.get('currentPrice', 1) or 1
        upside = ((value_per_share / max(current_price, 0.01)) - 1) * 100

        return {
            'value_per_share': value_per_share,
            'current_price': current_price,
            'upside': upside,
            'enterprise_value': enterprise_value,
            'equity_value': equity_value,
            'terminal_value': terminal_value,
            'recommendation': 'BUY' if upside > 15 else 'HOLD' if upside > -15 else 'SELL'
        }
    except Exception as e:
        return None

# ============================================================================
# STOCK SCREENER APP - TAB SYSTEM
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

    # MAIN APP
    st.title("📈 Financial Screener Dashboard")
    st.markdown("Analizza le migliori opportunità di investimento con criteri tecnici avanzati")

    # Main controls
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        if st.button("🔄 Aggiorna Dati", type="primary", use_container_width=True):
            st.info("Funzione TradingView screener - Disponibile nei prossimi aggiornamenti")

    with col2:
        if st.button("🧹 Pulisci Cache", use_container_width=True):
            st.success("✅ Cache pulita!")

    with col3:
        auto_refresh = st.checkbox("🔄 Auto-refresh (30s)")
        if auto_refresh:
            time.sleep(30)
            st.rerun()

    # TAB SYSTEM
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard TradingView", "🎯 Top Picks", "🔍 Analisi yfinance"])

    with tab1:
        st.subheader("Dashboard TradingView Screener")
        st.info("📊 Aggiornaclicca 'Aggiorna Dati' per caricare il screener da TradingView")

    with tab2:
        st.subheader("Top 5 Investment Picks")
        st.info("🎯 I top 5 ticker verranno mostrati qui dopo l'aggiornamento dei dati")

    with tab3:
        st.subheader("🔍 Analisi Multi-Agente Avanzata (yfinance)")
        st.markdown("Cerca un ticker e ottieni analisi completa con Entry/SL/TP basati su volatilità")

        # Search bar
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

        # Quick suggestions
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

        # Main search logic
        if (ticker_input and search_btn) or st.session_state.get("last_analyzed_ticker") != ticker_input.upper():

            if ticker_input.strip():
                st.session_state["last_analyzed_ticker"] = ticker_input.upper()

                with st.spinner(f"📊 Analisi di {ticker_input.upper()} in corso..."):

                    # Fetch dati
                    ticker_data = fetch_yfinance_data(ticker_input.upper(), period="1y")

                    if ticker_data and ticker_data['info']:  # VERIFICA CHE ticker_data NON SIA NONE

                        # OVERVIEW GENERALE
                        st.markdown("---")
                        st.subheader("📈 Informazioni Generali")

                        info = ticker_data['info']
                        current_price = ticker_data['history']['Close'].iloc[-1] if len(ticker_data['history']) > 0 else 0

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

                        # ANALISI TECNICA
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

                        # Calcola segnali
                        signal = calculate_dynamic_trading_signals(
                            ticker_data['history'],
                            atr_multiplier_sl=atr_sl,
                            atr_multiplier_tp=atr_tp
                        )

                        if signal:
                            # Display segnale principale
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
                                st.metric(
                                    "Risk/Reward",
                                    f"1:{signal['risk_reward_ratio']:.2f}",
                                    rr_status
                                )

                            # Livelli di trading
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

                            # Notizie
                            st.markdown("---")
                            st.subheader("📰 Ultime Notizie")

                            if ticker_data['news']:
                                for i, news in enumerate(ticker_data['news'][:3], 1):
                                    with st.expander(f"📰 Notizia {i}"):
                                        if isinstance(news, dict):
                                            st.write(f"**Titolo:** {news.get('title', 'N/A')}")
                                            st.write(f"**Link:** {news.get('link', 'N/A')}")

                            # Disclaimer
                            st.info("""
                            ⚠️ **Disclaimer:**
                            - Questa analisi è solo a scopo educativo
                            - Non è consulenza finanziaria
                            - SL/TP sono calcolati automaticamente basati su volatilità
                            """)
                        else:
                            st.error("❌ Errore nel calcolo dei segnali")
                    else:
                        st.error(f"❌ Impossibile recuperare dati per {ticker_input.upper()}")

            else:
                st.warning("⚠️ Inserisci un ticker valido")

        else:
            st.markdown("""
            ## 🚀 Benvenuto in Analisi Multi-Agente!

            Questa sezione ti consente di analizzare qualsiasi titolo con:

            - ✅ **Stop Loss e Take Profit dinamici basati su volatilità (ATR)**
            - ✅ **Analisi tecnica avanzata**
            - ✅ **Ultime notizie**
            - ✅ **Esportazione dati**

            **👆 Inserisci un ticker nella barra di ricerca per iniziare!**
            """)
