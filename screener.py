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
from ai_agent import call_groq_api, escape_markdown_latex

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
    # Ritorna SOLO l'URL (senza HTML)
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

# ============================================================================
# FUNZIONI ANALISI FONDAMENTALE - AGGIUNGI PRIMA DI stock_screener_app()
# ============================================================================

def fetch_fundamental_data(symbol: str):
    """Recupera dati fondamentali per un ticker specifico da tutti i mercati."""
    from tradingview_screener import Query
    import numpy as np
    
    markets = [
        'america', 'australia', 'belgium', 'brazil', 'canada', 'chile', 'china', 'italy',
        'czech', 'denmark', 'egypt', 'estonia', 'finland', 'france', 'germany', 'greece',
        'hongkong', 'hungary', 'india', 'indonesia', 'ireland', 'israel', 'japan', 'korea',
        'kuwait', 'lithuania', 'luxembourg', 'malaysia', 'mexico', 'morocco', 'netherlands',
        'newzealand', 'norway', 'peru', 'philippines', 'poland', 'portugal', 'qatar', 'russia',
        'singapore', 'slovakia', 'spain', 'sweden', 'switzerland', 'taiwan', 'uae', 'uk',
        'venezuela', 'vietnam', 'crypto'
    ]
    
    columns = [
        'name', 'description', 'country', 'sector', 'close','currency',
        'market_cap_basic', 'total_revenue_yoy_growth_fy', 'gross_profit_yoy_growth_fy',
        'net_income_yoy_growth_fy', 'earnings_per_share_diluted_yoy_growth_fy',
        'price_earnings_ttm', 'price_free_cash_flow_ttm', 'total_assets',
        'total_debt', 'operating_margin', 'ebitda_yoy_growth_fy',
        'net_margin_ttm', 'free_cash_flow_yoy_growth_fy', 'price_sales_ratio','total_liabilities_fy','total_current_assets',
        'capex_per_share_ttm','ebitda','ebit_ttm','net_income','effective_interest_rate_on_debt_fy', 'capital_expenditures_yoy_growth_ttm', 
        'enterprise_value_to_free_cash_flow_ttm', 'free_cash_flow_cagr_5y', 
        'invent_turnover_current', 'price_target_low', 'price_target_high', 
        'price_target_median', 'revenue_forecast_fq', 'earnings_per_share_forecast_fq',
        'SMA50', 'SMA200','beta_1_year','beta_2_year'
    ]
    
    try:
        query = Query().set_markets(*markets).set_tickers(symbol).select(*columns)
        total, df = query.get_scanner_data()
        
        if df.empty:
            st.warning(f"❌ Nessun dato trovato per {symbol}")
            return pd.DataFrame()
        
        df_filtered = df.head(1).copy()
        
        # Normalizza colonne mancanti
        for col in columns:
            if col not in df_filtered.columns:
                df_filtered[col] = np.nan
        
        return df_filtered
        
    except Exception as e:
        st.error(f"Errore nel caricamento dati fondamentali: {e}")
        return pd.DataFrame()


    
    # Se nessun formato ha funzionato
    st.error(f"❌ Nessun dato trovato per '{symbol}' nei formati NASDAQ:{symbol}, NYSE:{symbol}, AMEX:{symbol}")
    st.info("""
    💡 **Suggerimenti**:
    - Prova a cercare il ticker su TradingView.com prima
    - Inserisci direttamente il formato completo (es. 'NASDAQ:AAPL')
    - Verifica che sia un titolo del mercato USA
    - Esempi che funzionano: NASDAQ:AAPL, NYSE:JPM, NASDAQ:TSLA
    """)
    
    return pd.DataFrame()

def generate_fundamental_ai_report(company_name: str, fundamentals: dict):
    """Genera report AI usando i dati fondamentali disponibili."""
    try:
        # Filtra solo dati validi
        relevant_data = {k: v for k, v in fundamentals.items() 
                        if not pd.isna(v) and v != "" and k != 'ticker'}
        
        prompt = f"""
Sei un analista finanziario esperto. Analizza l'azienda '{company_name}' basandoti sui seguenti dati fondamentali:

{relevant_data}

Scrivi un REPORT PROFESSIONALE strutturato con:

## 1. SINTESI ESECUTIVA
Panoramica generale dell'azienda e posizionamento di mercato (100 parole)

## 2. ANALISI FINANZIARIA
Valuta ricavi, profitti, margini, crescita YoY (150 parole)

## 3. VALUTAZIONE E MULTIPLI
Analizza P/E, P/FCF, Price/Sales e altri multipli (120 parole)

## 4. SOLIDITÀ PATRIMONIALE
Commenta attività totali, debito, cash flow (100 parole)

## 5. TARGET PRICE E PREVISIONI
Analizza price target e forecast degli analisti (100 parole)
Utilizza analisi DCF (discounted cash flow) per stimare target price e delta dal prezzo attuale.

## 6. PROSPETTIVE E RACCOMANDAZIONI
Outlook complessivo e raccomandazione di investimento (130 parole)

IMPORTANTE:
- Usa il nome della valuta invece del simbolo
- Scrivi "miliardi" o "milioni" per i grandi numeri
- Evita underscore nei termini tecnici
- Mantieni tono professionale e basato sui dati disponibili
- Se un dato manca, NON inventare, concentrati su quelli disponibili
"""
        
        ai_report = call_groq_api(prompt, max_tokens=2000)
        return ai_report
        
    except Exception as e:
        return f"❌ Errore nella generazione del report AI: {str(e)}"


def process_fundamental_results(df_result, symbol):
    """Processa e mostra i risultati dell'analisi fondamentale."""
    row = df_result.iloc[0]
    company_name = row.get('description', symbol.upper())
    
    st.subheader(f"📈 {company_name} ({row.get('name', symbol)})")
    st.caption(f"Settore: {row.get('sector', 'N/A')} | Paese: {row.get('country', 'N/A')}")
    
    # Tabella dati fondamentali
    st.markdown("### 💼 Dati Fondamentali")
    excluded_cols = ['name', 'description', 'sector', 'country']
    display_cols = [c for c in df_result.columns if c not in excluded_cols]
    st.dataframe(df_result[display_cols].T, use_container_width=True, height=400)
    
    # Report AI fondamentale
    st.markdown("---")
    st.markdown("### 🧠 Analisi AI dei Bilanci")
    if st.button("🤖 Genera Report AI", key="generate_fundamental_report_btn"):
        with st.spinner("Generazione report AI..."):
            data_dict = row.to_dict()
            # Chiama la funzione AI per i fondamentali
            ai_report = generate_fundamental_ai_report(company_name, data_dict)
            
            if "❌" not in ai_report:
                st.success("✅ Report AI generato.")
                with st.expander("📄 Report Completo", expanded=True):
                    st.markdown(ai_report)
                
                # Download report
                clean_report = ai_report.replace("\\$", "$").replace("\\_", "_")
                st.download_button(
                    label="📥 Scarica Report AI",
                    data=clean_report,
                    file_name=f"Fundamental_Report_{company_name}_{datetime.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain",
                    key="download_fundamental_report_btn"
                )
            else:
                st.error("❌ Errore nella generazione del report AI.")
                st.info("💡 Riprova più tardi o verifica la connessione API.")

def fetch_technical_data(ticker: str):
    """
    Recupera i dati tecnici completi da TradingView per un ticker specifico.
    Utilizza oltre 50 parametri per analisi robusta.
    
    Ritorna un dizionario con i dati della prima riga trovata.
    """
    try:
        # Definisci i mercati dove cercare
        markets = [
            'america', 'australia', 'belgium', 'brazil', 'canada', 'chile', 'china', 'italy',
            'czech', 'denmark', 'egypt', 'estonia', 'finland', 'france', 'germany', 'greece',
            'hongkong', 'hungary', 'india', 'indonesia', 'ireland', 'israel', 'japan', 'korea',
            'kuwait', 'lithuania', 'luxembourg', 'malaysia', 'mexico', 'morocco', 'netherlands',
            'newzealand', 'norway', 'peru', 'philippines', 'poland', 'portugal', 'qatar', 'russia',
            'singapore', 'slovakia', 'spain', 'sweden', 'switzerland', 'taiwan', 'uae', 'uk',
            'venezuela', 'vietnam', 'crypto'
        ]
        
        # Query completa per analisi tecnica
        query = (Query()
            .set_markets(*markets)
            .set_tickers(ticker)
            .select(
                # Prezzo e Volume base
                'name', 'close', 'open', 'high', 'low', 'volume',
                'change', 'change_abs', 'Recommend.All', 'description', 'country', 'sector',
                
                # Indicatori di Trend
                'RSI', 'RSI[1]', 'Stoch.K', 'Stoch.D', 
                'MACD.macd', 'MACD.signal', 'ADX', 'ADX+DI', 'ADX-DI',
                'CCI20', 'Mom', 'Stoch.RSI.K',
                
                # Medie Mobili
                'SMA20', 'EMA20', 'SMA50', 'EMA50', 'SMA100', 'SMA200',
                'EMA10', 'EMA30',
                
                # Volatilità
                'ATR', 'BB.upper', 'BB.lower', 'BB.basis',
                'average_true_range',
                
                # Volume
                'average_volume_10d_calc', 'average_volume_30d_calc',
                'average_volume_60d_calc', 'relative_volume_10d_calc',
                
                # Pivot Points
                'Pivot.M.Classic.S1', 'Pivot.M.Classic.R1',
                'Pivot.M.Classic.S2', 'Pivot.M.Classic.R2',
                'Pivot.M.Classic.S3', 'Pivot.M.Classic.R3',
                'Pivot.M.Classic.Middle',
                
                # Performance
                'Perf.W', 'Perf.1M', 'Perf.3M', 'Perf.6M', 'Perf.Y',
                
                # Volatilità Storica
                'Volatility.D', 'Volatility.W', 'Volatility.M',
                
                # Dati Fondamentali Base
                'market_cap_basic'
            )
        )
        
        # Esegui la query - ritorna (total, dataframe)
        total, df = query.get_scanner_data()
        
        # Se il dataframe non è vuoto, ritorna il primo risultato come dizionario
        if df is not None and not df.empty:
            return df.iloc[0].to_dict()
        else:
            return None
            
    except Exception as e:
        st.error(f"❌ Errore nel recupero dati tecnici: {str(e)}")
        return None

def generate_technical_ai_report(ticker: str, technical_dict) -> str:
    """
    Genera analisi AI completa utilizzando Groq tramite callgroqapi.
    Fornisce raccomandazioni su entry, stop loss e take profit.
    """
    
    # Prepara il prompt strutturato
    prompt = f"""Sei un analista tecnico esperto specializzato in trading algoritmico. Analizza il ticker {ticker} e fornisci un report dettagliato e AZIONABILE.

DATI TECNICI ATTUALI:
- Ticker: {technical_data.get('name', 'N/A')}
- Azienda: {technical_data.get('description', 'N/A')}
- Settore: {technical_data.get('sector', 'N/A')}
- Prezzo Corrente: ${technical_data.get('close', 0):.2f}
- Variazione: {technical_data.get('change', 0):.2f}%
- Volume: {format_currency(technical_data.get('volume', 0), '$')}
- Volume Medio 10g: {format_currency(technical_data.get('average_volume_10d_calc', 0), '$')}
- Volume Relativo: {technical_data.get('relative_volume_10d_calc', 0):.2f}x

INDICATORI DI TREND:
- RSI(14): {technical_data.get('RSI', 0):.2f}
- RSI Precedente: {technical_data.get('RSI[1]', 0):.2f}
- MACD: {technical_data.get('MACD.macd', 0):.4f}
- MACD Signal: {technical_data.get('MACD.signal', 0):.4f}
- ADX: {technical_data.get('ADX', 0):.2f}
- ADX +DI: {technical_data.get('ADX+DI', 0):.2f}
- ADX -DI: {technical_data.get('ADX-DI', 0):.2f}
- Stochastic K: {technical_data.get('Stoch.K', 0):.2f}
- Stochastic D: {technical_data.get('Stoch.D', 0):.2f}
- CCI(20): {technical_data.get('CCI20', 0):.2f}
- Momentum: {technical_data.get('Mom', 0):.2f}

MEDIE MOBILI:
- EMA10: ${technical_data.get('EMA10', 0):.2f}
- SMA20: ${technical_data.get('SMA20', 0):.2f}
- EMA20: ${technical_data.get('EMA20', 0):.2f}
- EMA30: ${technical_data.get('EMA30', 0):.2f}
- SMA50: ${technical_data.get('SMA50', 0):.2f}
- SMA100: ${technical_data.get('SMA100', 0):.2f}
- SMA200: ${technical_data.get('SMA200', 0):.2f}

VOLATILITÀ E BANDE:
- ATR: ${technical_data.get('atr', 0):.4f}
- ATR Percentuale: {technical_data.get('atr_pct', 0):.2f}%
- Volatilità Giornaliera: {technical_data.get('vol_daily', 0):.2f}%
- Volatilità Settimanale: {technical_data.get('vol_weekly', 0):.2f}%
- Volatilità Mensile: {technical_data.get('vol_monthly', 0):.2f}%
- Bollinger Upper: ${technical_data.get('BB.upper', 0):.2f}
- Bollinger Middle: ${technical_data.get('BB.basis', 0):.2f}
- Bollinger Lower: ${technical_data.get('BB.lower', 0):.2f}
- BB Width: {technical_data.get('bb_width_pct', 0):.2f}%

PIVOT POINTS MENSILI:
- Resistenza 3: ${technical_data.get('Pivot.M.Classic.R3', 0):.2f}
- Resistenza 2: ${technical_data.get('Pivot.M.Classic.R2', 0):.2f}
- Resistenza 1: ${technical_data.get('Pivot.M.Classic.R1', 0):.2f}
- Pivot Middle: ${technical_data.get('Pivot.M.Classic.Middle', 0):.2f}
- Supporto 1: ${technical_data.get('Pivot.M.Classic.S1', 0):.2f}
- Supporto 2: ${technical_data.get('Pivot.M.Classic.S2', 0):.2f}
- Supporto 3: ${technical_data.get('Pivot.M.Classic.S3', 0):.2f}

PERFORMANCE STORICA:
- 1 Settimana: {technical_data.get('Perf.W', 0):.2f}%
- 1 Mese: {technical_data.get('Perf.1M', 0):.2f}%
- 3 Mesi: {technical_data.get('Perf.3M', 0):.2f}%
- 6 Mesi: {technical_data.get('Perf.6M', 0):.2f}%
- 1 Anno: {technical_data.get('Perf.Y', 0):.2f}%

RACCOMANDAZIONE AGGREGATA: {format_technical_rating(technical_data.get('Recommend.All', 0))}
Score Numerico: {technical_data.get('Recommend.All', 0):.3f}

---

Fornisci un'analisi STRUTTURATA PROFESSIONALE nel seguente formato (usa markdown):

## 1. SINTESI ESECUTIVA
[Panoramica rapida: trend principale, sentiment del mercato, opportunità/rischi immediati - max 80 parole]

## 2. ANALISI TECNICA APPROFONDITA

### Trend e Direzione
[Analisi completa del trend usando medie mobili, ADX, e price action - 120 parole]

### Momentum"""



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
    
    # --- MAIN APP CON TAB SYSTEM ---
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
                
                st.success(f"✅ Aggiornati {len(new_data)} titoli)")
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
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "🎯 Top Picks", "📕 Fundamentals", "📈 Technicals"])
    
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
                    display_df,
                    column_config={
                        "Chart": st.column_config.LinkColumn(
                            "Chart",
                            display_text="📊 View"
                        )
                    },
                    use_container_width=True,
                    height=400,
                    hide_index=True
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
- **🔍 Ricerca TradingView**: Cerca e visualizza grafici di qualsiasi titolo

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
    
    #========== TAB 3: ANALISI FONDAMENTALE =========
    
    with tab3:
        st.header("📊 Analisi Fondamentale Azienda")
        st.markdown("Cerca un'azienda specifica e ottieni un'analisi AI completa dei suoi bilanci")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            symbol = st.text_input(
                "Inserisci Simbolo con prefisso (es. NASDAQ:AAPL, MIL:ENEL):", 
                "", 
                key="fundamental_search_input",
                help="Formato richiesto: EXCHANGE:TICKER",
                placeholder="Es. NASDAQ:AAPL"
            )
        
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            analyze_btn = st.button(
                "📊 Analizza", 
                key="analyze_fundamentals_btn",
                type="primary",
                use_container_width=True
            )
        
        # Esempi rapidi
        st.markdown("**Esempi rapidi:**")
        col_ex1, col_ex2, col_ex3, col_ex4 = st.columns(4)
        
        examples = [
            ("📱 Apple", "NASDAQ:AAPL"),
            ("⚡ Tesla", "NASDAQ:TSLA"),
            ("💡 Enel", "MIL:ENEL"),
            ("🏦 Intesa SP", "MIL:ISP")
        ]
        
        for i, (label, ticker_val) in enumerate(examples):
            with [col_ex1, col_ex2, col_ex3, col_ex4][i]:
                if st.button(label, key=f"fund_ex_{i}", use_container_width=True):
                    symbol = ticker_val
                    analyze_btn = True

        
        if symbol and analyze_btn:
            with st.spinner(f"🔍 Ricerca dati fondamentali per {symbol.upper()}..."):
                df_result = fetch_fundamental_data(symbol.upper())
                
                if not df_result.empty:
                    st.success(f"✅ Dati trovati per {symbol}")
                    
                    # Mostra dati completi
                    st.subheader("📊 Dati Completi")
                    st.dataframe(df_result, use_container_width=True)
                    
                    # Tabella presenza dati
                    st.subheader("📋 Presenza Dati per Colonna")
                    data_info = []
                    for col in df_result.columns:
                        if col != 'ticker':
                            value = df_result.iloc[0].get(col, None)
                            is_present = not pd.isna(value) and value != ""
                            stato = "✅ Presente" if is_present else "❌ Assente"
                            valore = value if is_present else "N/A"
                            data_info.append({
                                'Colonna': col,
                                'Stato': stato,
                                'Valore': valore
                            })
                    
                    presence_df = pd.DataFrame(data_info)
                    st.dataframe(presence_df, use_container_width=True)
                    
                    # Genera report AI usando i dati disponibili
                    st.subheader("🤖 Report AI Fondamentale")
                    
                    with st.spinner("🧠 Generazione analisi AI..."):
                        # Prepara dati per AI
                        fundamental_dict = df_result.iloc[0].to_dict()
                        
                        # Genera report AI
                        ai_report = generate_fundamental_ai_report(
                            company_name=fundamental_dict.get('name', symbol),
                            fundamentals=fundamental_dict
                        )
                        
                        st.markdown(escape_markdown_latex(ai_report))
                    
                    # Pulsante download
                    st.download_button(
                        label="📥 Scarica Report Completo",
                        data=ai_report,
                        file_name=f"report_fondamentale_{symbol}.txt",
                        mime="text/plain"
                    )

    # ========== TAB 4: ANALISI TECNICA AVANZATA ==========
    with tab4:
        st.header("📊 Analisi Tecnica Avanzata con AI")
        
        st.markdown("""
        Inserisci un ticker per ottenere un'**analisi tecnica completa generata dall'AI**, 
        includendo prezzi di ingresso ottimali, stop loss e take profit calcolati sulla volatilità effettiva (ATR).
        """)
        
        # Barra di ricerca ticker
        col1, col2 = st.columns([3, 1])
        
        with col1:
            ticker_input = st.text_input(
                "🔍 Ticker Symbol",
                placeholder="es. AAPL, TSLA, MSFT, ENEL.MI",
                key="technical_search_input",
                help="Inserisci il simbolo del ticker da analizzare. Per titoli italiani aggiungi .MI (es. ENEL.MI)"
            )
        
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            analyze_btn = st.button(
                "🚀 Analizza", 
                key="analyze_technical_btn", 
                type="primary", 
                use_container_width=True
            )
        
        # Esempi rapidi
        st.markdown("**Esempi rapidi:**")
        col_ex1, col_ex2, col_ex3, col_ex4 = st.columns(4)
        
        examples = [
            ("📱 Apple", "AAPL"),
            ("⚡ Tesla", "TSLA"),
            ("💡 Enel", "ENEL.MI"),
            ("🏦 Intesa SP", "ISP.MI")
        ]
        
        for i, (label, ticker_val) in enumerate(examples):
            with [col_ex1, col_ex2, col_ex3, col_ex4][i]:
                if st.button(label, key=f"tech_ex{i}", use_container_width=True):
                    ticker_input = ticker_val
                    analyze_btn = True
        
        # Esegui analisi quando il bottone viene premuto
        if ticker_input and analyze_btn:
            ticker = ticker_input.upper().strip()
            
            with st.spinner(f"🔄 Recupero dati tecnici per **{ticker}**..."):
                # Fetch dati tecnici
                technical_data = fetch_technical_data(ticker)
                
                if technical_data is None:
                    st.error(f"❌ Impossibile trovare dati per il ticker **'{ticker}'**.")
                    st.info("""
                    **Suggerimenti:**
                    - Verifica che il simbolo sia corretto
                    - Per titoli italiani usa il formato: TICKER.MI (es. ENEL.MI)
                    - Per titoli USA non serve aggiungere exchange
                    - Prova a cercare il ticker su TradingView.com prima
                    """)
                    st.stop()
                
                # Calcola metriche volatilità
                technical_data = calculate_technical_data(technical_data)
                
                # Mostra dati principali
                st.success(f"✅ Dati recuperati per **{technical_data.get('description', ticker)}** ({ticker})")
                
                # Dashboard metriche rapide
                st.markdown("### 📈 Metriche Principali")
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    close_price = technical_data.get('close', 0)
                    change_pct = technical_data.get('change', 0)
                    st.metric(
                        "Prezzo Attuale",
                        f"${close_price:.2f}",
                        f"{change_pct:+.2f}%",
                        delta_color="normal"
                    )
                
                with col2:
                    rsi = technical_data.get('RSI', 0)
                    rsi_status = "🔴 Ipercomprato" if rsi > 70 else "🟢 Ipervenduto" if rsi < 30 else "🟡 Neutrale"
                    st.metric(
                        "RSI(14)",
                        f"{rsi:.1f}",
                        rsi_status
                    )
                
                with col3:
                    atr = technical_data.get('atr', 0)
                    atr_pct = technical_data.get('atr_pct', 0)
                    st.metric(
                        "ATR (Volatilità)",
                        f"${atr:.2f}",
                        f"{atr_pct:.2f}%"
                    )
                
                with col4:
                    volume_rel = technical_data.get('relative_volume_10d_calc', 0)
                    vol_status = "🔥 Alto" if volume_rel > 1.5 else "📊 Normale" if volume_rel > 0.7 else "📉 Basso"
                    st.metric(
                        "Volume Relativo",
                        f"{volume_rel:.2f}x",
                        vol_status
                    )
                
                with col5:
                    recommend = technical_data.get('Recommend.All', 0)
                    rec_label = format_technical_rating(recommend)
                    st.metric(
                        "Rating Tecnico",
                        rec_label,
                        f"{recommend:.2f}"
                    )
                
                st.divider()
                
                # Sezione indicatori dettagliati
                with st.expander("📊 Indicatori Tecnici Dettagliati", expanded=False):
                    col_ind1, col_ind2, col_ind3 = st.columns(3)
                    
                    with col_ind1:
                        st.markdown("**🎯 Oscillatori**")
                        st.write(f"- RSI: {technical_data.get('RSI', 0):.2f}")
                        st.write(f"- Stoch K: {technical_data.get('Stoch.K', 0):.2f}")
                        st.write(f"- Stoch D: {technical_data.get('Stoch.D', 0):.2f}")
                        st.write(f"- CCI(20): {technical_data.get('CCI20', 0):.2f}")
                        st.write(f"- Momentum: {technical_data.get('Mom', 0):.2f}")
                    
                    with col_ind2:
                        st.markdown("**📈 Medie Mobili**")
                        st.write(f"- SMA20: ${technical_data.get('SMA20', 0):.2f}")
                        st.write(f"- SMA50: ${technical_data.get('SMA50', 0):.2f}")
                        st.write(f"- SMA200: ${technical_data.get('SMA200', 0):.2f}")
                        st.write(f"- EMA20: ${technical_data.get('EMA20', 0):.2f}")
                        st.write(f"- EMA50: ${technical_data.get('EMA50', 0):.2f}")
                    
                    with col_ind3:
                        st.markdown("**📊 MACD & Trend**")
                        macd = technical_data.get('MACD.macd', 0)
                        signal = technical_data.get('MACD.signal', 0)
                        st.write(f"- MACD: {macd:.4f}")
                        st.write(f"- Signal: {signal:.4f}")
                        st.write(f"- Histogram: {(macd - signal):.4f}")
                        st.write(f"- ADX: {technical_data.get('ADX', 0):.2f}")
                
                # Sezione Bollinger Bands e Pivot
                with st.expander("🎯 Supporti, Resistenze e Bollinger Bands", expanded=False):
                    col_sr1, col_sr2 = st.columns(2)
                    
                    with col_sr1:
                        st.markdown("**🔴 Resistenze (Pivot Mensili)**")
                        st.write(f"- R3: ${technical_data.get('Pivot.M.Classic.R3', 0):.2f}")
                        st.write(f"- R2: ${technical_data.get('Pivot.M.Classic.R2', 0):.2f}")
                        st.write(f"- R1: ${technical_data.get('Pivot.M.Classic.R1', 0):.2f}")
                        st.write(f"- Pivot: ${technical_data.get('Pivot.M.Classic.Middle', 0):.2f}")
                    
                    with col_sr2:
                        st.markdown("**🟢 Supporti (Pivot Mensili)**")
                        st.write(f"- S1: ${technical_data.get('Pivot.M.Classic.S1', 0):.2f}")
                        st.write(f"- S2: ${technical_data.get('Pivot.M.Classic.S2', 0):.2f}")
                        st.write(f"- S3: ${technical_data.get('Pivot.M.Classic.S3', 0):.2f}")
                        
                        st.markdown("**📊 Bollinger Bands**")
                        st.write(f"- Upper: ${technical_data.get('BB.upper', 0):.2f}")
                        st.write(f"- Middle: ${technical_data.get('BB.basis', 0):.2f}")
                        st.write(f"- Lower: ${technical_data.get('BB.lower', 0):.2f}")
                
                # Sezione Performance
                with st.expander("📅 Performance Storica", expanded=False):
                    perf_data = {
                        'Timeframe': ['1 Settimana', '1 Mese', '3 Mesi', '6 Mesi', '1 Anno'],
                        'Performance (%)': [
                            technical_data.get('Perf.W', 0),
                            technical_data.get('Perf.1M', 0),
                            technical_data.get('Perf.3M', 0),
                            technical_data.get('Perf.6M', 0),
                            technical_data.get('Perf.Y', 0)
                        ]
                    }
                    perf_df = pd.DataFrame(perf_data)
                    
                    # Crea grafico performance
                    fig_perf = px.bar(
                        perf_df,
                        x='Timeframe',
                        y='Performance (%)',
                        title=f'Performance Storica - {ticker}',
                        color='Performance (%)',
                        color_continuous_scale=['red', 'yellow', 'green']
                    )
                    fig_perf.update_traces(texttemplate='%{y:.2f}%', textposition='outside')
                    fig_perf.add_hline(y=0, line_dash="dash", line_color="black", line_width=1)
                    st.plotly_chart(fig_perf, use_container_width=True)
                
                st.divider()
                
                # Genera analisi AI
                st.markdown("### 🤖 Report AI Completo con Strategia Operativa")
                
                with st.spinner("🧠 Generazione analisi AI in corso (può richiedere 10-20 secondi)..."):
                    ai_analysis = generate_technical_ai_report(ticker, technical_data)
                    
                    if ai_analysis and "Errore" not in ai_analysis[:50]:
                        # Mostra il report con escape markdown se necessario
                        st.markdown(escape_markdown_latex(ai_analysis))
                        
                        # Bottoni di azione
                        col_btn1, col_btn2, col_btn3 = st.columns(3)
                        
                        with col_btn1:
                            # Bottone per scaricare il report
                            st.download_button(
                                label="📥 Scarica Report",
                                data=ai_analysis,
                                file_name=f"report_analisi_tecnica_{ticker}_{datetime.now().strftime('%Y%m%d')}.txt",
                                mime="text/plain",
                                use_container_width=True
                            )
                        
                        with col_btn2:
                            # Link a TradingView
                            tv_url = get_tradingview_url(ticker)
                            st.link_button(
                                f"📊 Vedi Grafico {ticker}",
                                tv_url,
                                use_container_width=True
                            )
                        
                        with col_btn3:
                            # Bottone per nuova analisi
                            if st.button("🔄 Nuova Analisi", key="new_analysis_btn", use_container_width=True):
                                st.rerun()
                        
                    else:
                        st.error("❌ Errore nella generazione del report AI")
                        st.info("Riprova tra qualche istante o verifica la connessione all'API Groq.")
                
                st.divider()
                
                # Sezione dati tecnici completi (espandibile)
                with st.expander("📋 Tutti i Dati Tecnici Grezzi (JSON)", expanded=False):
                    df_technical = pd.DataFrame([technical_data])
                    st.dataframe(df_technical.T, use_container_width=True)
        
        # Messaggio se non è stata fatta ancora nessuna ricerca
        elif not ticker_input:
            st.info("👆 Inserisci un ticker nella barra di ricerca sopra per iniziare l'analisi tecnica avanzata.")
            
            st.markdown("---")
            st.markdown("### 🎯 Caratteristiche dell'Analisi Tecnica AI")
            
            col_feat1, col_feat2 = st.columns(2)
            
            with col_feat1:
                st.markdown("""
                **📊 Indicatori Analizzati:**
                - ✅ Oltre 50 parametri tecnici da TradingView
                - ✅ RSI, MACD, Stocastico, ADX, CCI
                - ✅ Medie Mobili (SMA20/50/200, EMA10/20/30)
                - ✅ Bollinger Bands e ATR
                - ✅ Pivot Points mensili
                - ✅ Volatilità multi-timeframe
                - ✅ Volume relativo e performance storica
                """)
            
            with col_feat2:
                st.markdown("""
                **🎯 Output del Report AI:**
                - ✅ Analisi tecnica completa del trend
                - ✅ **Prezzo di ingresso ottimale**
                - ✅ **Stop Loss calcolato su ATR**
                - ✅ **3 livelli di Take Profit** con risk/reward
                - ✅ Strategia di gestione posizione
                - ✅ Position sizing raccomandato
                - ✅ Supporti e resistenze chiave
                - ✅ Timeframe consigliato
                """)

    # Summary
    current_date = datetime.now()
