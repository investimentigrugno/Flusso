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
from typing import List, Dict
import re
from ai_agent import call_groq_api, escape_markdown_latex
from fpdf import FPDF

def generate_pdf_report(title, content, filename_prefix):
    """Genera un PDF da contenuto markdown/testo"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Titolo
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, title, ln=True, align='C')
    pdf.ln(10)
    
    # Contenuto
    pdf.set_font("Arial", "", 11)
    
    # Pulisci il contenuto da caratteri speciali
    clean_content = content.replace('\\$', '$').replace('\\_', '_')
    clean_content = clean_content.encode('latin-1', 'replace').decode('latin-1')
    
    # Aggiungi contenuto riga per riga
    for line in clean_content.split('\n'):
        if line.startswith('##'):
            pdf.ln(5)
            pdf.set_font("Arial", "B", 14)
            pdf.multi_cell(0, 10, line.replace('##', '').strip())
            pdf.set_font("Arial", "", 11)
        elif line.startswith('#'):
            pdf.ln(5)
            pdf.set_font("Arial", "B", 15)
            pdf.multi_cell(0, 10, line.replace('#', '').strip())
            pdf.set_font("Arial", "", 11)
        elif line.strip():
            pdf.multi_cell(0, 6, line)
        else:
            pdf.ln(3)
    
    # Genera PDF in memoria
    pdf_output = pdf.output(dest='S').encode('latin-1')
    return pdf_output


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
    Ritorna un DataFrame con i dati della prima riga trovata.
    """
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
    
    columns = [
        # Info base
        'name', 'description', 'close', 'open', 'high', 'low', 'volume',
        'change', 'change_abs', 'Recommend.All',
        
        # Indicatori di Trend
        'RSI', 'RSI[1]', 'Stoch.K', 'Stoch.D', 
        'MACD.macd', 'MACD.signal', 'ADX', 'ADX+DI', 'ADX-DI',
        'CCI20', 'Mom', 'Stoch.RSI.K',
        
        # Medie Mobili
        'SMA20', 'EMA20', 'SMA50', 'EMA50', 'SMA100', 'SMA200',
        'EMA10', 'EMA30',
        
        # Volatilità
        'ATR', 'ATR[1]', 'BB.upper', 'BB.lower', 'BB.basis',
        'Volatility.D', 'Volatility.W', 'Volatility.M',
        
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
        
        # Dati Fondamentali Base
        'market_cap_basic', 'price_earnings_ttm', 'sector', 'country'
    ]
    
    try:
        query = Query().set_markets(*markets).set_tickers(ticker).select(*columns)
        total, df = query.get_scanner_data()
        
        if df.empty:
            st.warning(f"❌ Nessun dato trovato per {ticker}")
            return pd.DataFrame()
        
        df_filtered = df.head(1).copy()
        
        # Normalizza colonne mancanti
        for col in columns:
            if col not in df_filtered.columns:
                df_filtered[col] = np.nan
        
        return df_filtered
    
    except Exception as e:
        st.error(f"❌ Errore nel caricamento dati tecnici: {e}")
        return pd.DataFrame()


def generate_technical_ai_report(ticker: str, technical_dict: dict) -> str:
    """
    Genera analisi AI completa utilizzando Groq.
    Fornisce raccomandazioni su entry, stop loss e take profit.
    """
    
    # Filtra solo dati validi (come fai per i fondamentali)
    relevant_data = {k: v for k, v in technical_dict.items() 
                    if not pd.isna(v) and v != "" and k != 'name'}
    
    # Prepara il prompt strutturato
    prompt = f"""Sei un analista tecnico esperto specializzato in trading algoritmico. Analizza il ticker {ticker} e fornisci un report dettagliato e AZIONABILE.

DATI TECNICI DISPONIBILI:
{relevant_data}

Fornisci un'analisi STRUTTURATA PROFESSIONALE nel seguente formato (usa markdown):

## 1. SINTESI ESECUTIVA
Panoramica rapida: trend principale, sentiment del mercato, opportunità/rischi immediati (100 parole)

## 2. ANALISI TECNICA APPROFONDITA

### Trend e Direzione
Analisi completa del trend usando medie mobili, ADX, e price action (120 parole)

### Momentum e Oscillatori
Valutazione RSI, MACD, Stocastico, CCI - identificare divergenze e segnali (120 parole)

### Supporti e Resistenze
Analisi dei livelli chiave basati su pivot points, medie mobili, e Bollinger Bands (100 parole)

## 3. ANALISI VOLATILITÀ E RISK MANAGEMENT
Interpretazione ATR, volatilità multi-timeframe, implicazioni per sizing e holding period (100 parole)

## 4. RACCOMANDAZIONI OPERATIVE

**ATTENZIONE:** Fornisci SOLO lo scenario più probabile (LONG o SHORT), NON entrambi.

### Scenario Raccomandato: [LONG o SHORT]

**Prezzo di Ingresso Ottimale:** $[prezzo preciso]
- Razionale: [perché questo prezzo - es. rottura resistenza, pullback a supporto, etc.]

**Stop Loss:** $[prezzo preciso]
- Distanza: [percentuale e ATR multipli dal prezzo di ingresso]
- Razionale: [perché questo livello invalida lo scenario]

**Take Profit 1 (Target Conservativo):** $[prezzo preciso]
- Potenziale Gain: [percentuale]
- Risk/Reward Ratio: [es. 1:1.8]
- Chiudere: 40% della posizione

**Take Profit 2 (Target Intermedio):** $[prezzo preciso]
- Potenziale Gain: [percentuale]
- Risk/Reward Ratio: [es. 1:3.2]
- Chiudere: 40% della posizione

**Take Profit 3 (Target Esteso):** $[prezzo preciso]
- Potenziale Gain: [percentuale]
- Risk/Reward Ratio: [es. 1:5.5]
- Chiudere: 20% della posizione o trailing stop

**Strategia di Gestione:**
Descrivi come gestire la posizione: quando spostare lo stop a breakeven, quando usare trailing stop, etc. (80 parole)

## 5. GESTIONE DEL RISCHIO

**Position Sizing Raccomandato:** [X]% del capitale totale
- Giustificazione: [basato su volatilità e livello di confidenza]

**Livello di Invalidazione:** $[prezzo]
- Se il prezzo raggiunge questo livello, lo scenario è compromesso

**Timeframe Consigliato:** [es. 2-4 settimane, swing trading]

**Note di Risk Management:**
Considerazioni specifiche sulla volatilità, eventi macroeconomici in arrivo, earnings, etc. (60 parole)

## 6. LIVELLI CHIAVE DA MONITORARE

**Supporti Critici:**
1. $[prezzo] - [descrizione]
2. $[prezzo] - [descrizione]
3. $[prezzo] - [descrizione]

**Resistenze Critiche:**
1. $[prezzo] - [descrizione]
2. $[prezzo] - [descrizione]
3. $[prezzo] - [descrizione]

## 7. CONCLUSIONI E RACCOMANDAZIONE FINALE

**Outlook:** [Bullish/Bearish/Neutrale]
**Livello di Confidenza:** [Alto/Medio/Basso] - [percentuale estimata]
**Orizzonte Temporale:** [giorni/settimane]

Sintesi finale con call-to-action chiara (60 parole)

---

ISTRUZIONI CRITICHE:
- Basa TUTTI i calcoli di SL e TP sulla volatilità effettiva (ATR) del titolo
- Utilizza questi moltiplicatori ATR standard:
  * Stop Loss: 1.5-2.0x ATR dal prezzo di ingresso
  * TP1: 2.5-3.5x ATR (ratio minimo 1:1.5)
  * TP2: 4-6x ATR (ratio minimo 1:2.5)
  * TP3: 7-10x ATR (solo se il trend è molto forte e ADX > 25)
- Fornisci SOLO prezzi numerici specifici, MAI range vaghi tipo "$45-47"
- NON inventare dati - usa solo quelli forniti
- Se un dato manca, dichiaralo esplicitamente
- Mantieni tono professionale ma accessibile
- NON usare underscore nei termini (scrivi "stop loss" non "stop_loss")
"""

    try:
        # Chiamata API Groq tramite la funzione esistente
        ai_report = call_groq_api(prompt, max_tokens=3500)
        return ai_report
        
    except Exception as e:
        return f"❌ Errore nella generazione del report AI: {str(e)}"

def process_technical_results(df_result, ticker):
    """Processa e mostra i risultati dell'analisi tecnica."""
    row = df_result.iloc[0]
    company_name = row.get('description', ticker.upper())
    
    st.subheader(f"📊 {company_name} ({row.get('name', ticker)})")
    st.caption(f"Settore: {row.get('sector', 'N/A')} | Paese: {row.get('country', 'N/A')}")
    
    # Dashboard metriche rapide
    st.markdown("### 📈 Metriche Principali")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        close_price = row.get('close', 0)
        change_pct = row.get('change', 0)
        st.metric(
            "Prezzo Attuale",
            f"${close_price:.2f}",
            f"{change_pct:+.2f}%",
            delta_color="normal"
        )
    
    with col2:
        rsi = row.get('RSI', 0)
        rsi_status = "🔴 Ipercomprato" if rsi > 70 else "🟢 Ipervenduto" if rsi < 30 else "🟡 Neutrale"
        st.metric(
            "RSI(14)",
            f"{rsi:.1f}",
            rsi_status
        )
    
    with col3:
        atr = row.get('ATR', 0)
        volatility_d = row.get('Volatility.D', 0)
        st.metric(
            "ATR (Volatilità)",
            f"${atr:.2f}",
            f"Vol: {volatility_d:.2f}%"
        )
    
    with col4:
        volume_rel = row.get('relative_volume_10d_calc', 0)
        vol_status = "🔥 Alto" if volume_rel > 1.5 else "📊 Normale" if volume_rel > 0.7 else "📉 Basso"
        st.metric(
            "Volume Relativo",
            f"{volume_rel:.2f}x",
            vol_status
        )
    
    with col5:
        recommend = row.get('Recommend.All', 0)
        rec_label = format_technical_rating(recommend)
        st.metric(
            "Rating Tecnico",
            rec_label,
            f"{recommend:.2f}"
        )
    
    # Tabella dati tecnici completi
    st.markdown("---")
    st.markdown("### 💼 Dati Tecnici Completi")
    excluded_cols = ['name', 'description', 'sector', 'country']
    display_cols = [c for c in df_result.columns if c not in excluded_cols]
    st.dataframe(df_result[display_cols].T, use_container_width=True, height=400)
    
    # Report AI tecnico
    st.markdown("---")
    st.markdown("### 🧠 Analisi AI Tecnica con Strategia Operativa")
    if st.button("🤖 Genera Report AI Tecnico", key="generate_technical_report_btn"):
        with st.spinner("Generazione report AI tecnico in corso..."):
            data_dict = row.to_dict()
            # Chiama la funzione AI per l'analisi tecnica
            ai_report = generate_technical_ai_report(ticker, data_dict)
            
            if "❌" not in ai_report:
                st.success("✅ Report AI tecnico generato.")
                with st.expander("📄 Report Completo", expanded=True):
                    st.markdown(escape_markdown_latex(ai_report))
                
                # Download report
                st.download_button(
                    label="📥 Scarica Report AI",
                    data=ai_report,
                    file_name=f"Technical_Report_{ticker}_{datetime.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain",
                    key="download_technical_report_btn"
                )
            else:
                st.error("❌ Errore nella generazione del report AI.")
                st.info("💡 Riprova più tardi o verifica la connessione API.")



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
                    
                    # Genera PDF
                    pdf_bytes = generate_pdf_report(
                        title=f"Analisi Fondamentale - {company_name}",
                        content=ai_report,
                        filename_prefix="Fundamental_Report"
                    )

                    col_pdf, col_txt = st.columns(2)

                    with col_pdf:
                        st.download_button(
                            label="📥 Scarica Report PDF",
                            data=pdf_bytes,
                            file_name=f"Fundamental_Report_{company_name}_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                            key="download_fundamental_pdf_btn",
                            type="primary",
                            use_container_width=True
                        )

                    with col_txt:
                        st.download_button(
                            label="📄 Scarica TXT",
                            data=ai_report,
                            file_name=f"Fundamental_Report_{company_name}_{datetime.now().strftime('%Y%m%d')}.txt",
                            mime="text/plain",
                            key="download_fundamental_txt_btn",
                            use_container_width=True
                        )


    # ========== TAB 4: ANALISI TECNICA AVANZATA ==========
    with tab4:
        st.header("📊 Analisi Tecnica Avanzata")
        st.markdown("Cerca un'azienda specifica e ottieni un'analisi tecnica completa con strategia operativa")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            ticker = st.text_input(
                "Inserisci Simbolo con prefisso (es. NASDAQ:AAPL, MIL:ENEL):", 
                "", 
                key="technical_search_input",
                help="Formato: TICKER o TICKER.MI per titoli italiani",
                placeholder="Es. NASDAQ:AAPL"
            )
        
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            analyze_btn_tech = st.button(
                "📊 Analizza", 
                key="analyze_technical_btn",
                type="primary",
                use_container_width=True
            )
        
        # Esempi rapidi
        st.markdown("**Esempi rapidi:**")
        col_ex1, col_ex2, col_ex3, col_ex4 = st.columns(4)
        
        examples_tech = [
            ("📱 Apple", "NASDAQ:AAPL"),
            ("⚡ Tesla", "NASDAQ:TSLA"),
            ("💡 Enel", "MIL:ENEL"),
            ("🏦 Intesa SP", "MIL:ISP")
        ]
        
        for i, (label, ticker_val) in enumerate(examples_tech):
            with [col_ex1, col_ex2, col_ex3, col_ex4][i]:
                if st.button(label, key=f"tech_ex_{i}", use_container_width=True):
                    ticker = ticker_val
                    analyze_btn_tech = True
        
        if ticker and analyze_btn_tech:
            with st.spinner(f"🔍 Ricerca dati tecnici per {ticker.upper()}..."):
                df_result = fetch_technical_data(ticker.upper())
                
                if not df_result.empty:
                    st.success(f"✅ Dati trovati per {ticker}")
                    
                    # Dashboard metriche rapide
                    st.subheader("📈 Metriche Principali")
                    row = df_result.iloc[0]
                    
                    col1, col2, col3, col4, col5 = st.columns(5)
                    
                    with col1:
                        close_price = row.get('close', 0)
                        change_pct = row.get('change', 0)
                        st.metric(
                            "Prezzo Attuale",
                            f"${close_price:.2f}",
                            f"{change_pct:+.2f}%",
                            delta_color="normal"
                        )
                    
                    with col2:
                        rsi = row.get('RSI', 0)
                        rsi_status = "🔴 Ipercomprato" if rsi > 70 else "🟢 Ipervenduto" if rsi < 30 else "🟡 Neutrale"
                        st.metric(
                            "RSI(14)",
                            f"{rsi:.1f}",
                            rsi_status
                        )
                    
                    with col3:
                        atr = row.get('ATR', 0)
                        volatility_d = row.get('Volatility.D', 0)
                        st.metric(
                            "ATR (Volatilità)",
                            f"${atr:.2f}",
                            f"Vol: {volatility_d:.2f}%"
                        )
                    
                    with col4:
                        volume_rel = row.get('relative_volume_10d_calc', 0)
                        vol_status = "🔥 Alto" if volume_rel > 1.5 else "📊 Normale" if volume_rel > 0.7 else "📉 Basso"
                        st.metric(
                            "Volume Relativo",
                            f"{volume_rel:.2f}x",
                            vol_status
                        )
                    
                    with col5:
                        recommend = row.get('Recommend.All', 0)
                        rec_label = format_technical_rating(recommend)
                        st.metric(
                            "Rating Tecnico",
                            rec_label,
                            f"{recommend:.2f}"
                        )
                    
                    # Mostra dati completi
                    st.subheader("📊 Dati Completi")
                    st.dataframe(df_result, use_container_width=True)
                    
                    # Tabella presenza dati
                    st.subheader("📋 Presenza Dati per Colonna")
                    data_info = []
                    for col in df_result.columns:
                        if col not in ['name', 'description']:
                            value = df_result.iloc[0].get(col, None)
                            is_present = not pd.isna(value) and value != "" and value is not None
                            stato = "✅ Presente" if is_present else "❌ Assente"
                            
                            # Formatta il valore
                            if is_present:
                                if isinstance(value, float):
                                    if abs(value) >= 1e9:
                                        valore = f"{value:,.2f}"
                                    elif abs(value) >= 1:
                                        valore = f"{value:.4f}"
                                    else:
                                        valore = f"{value:.6f}"
                                else:
                                    valore = str(value)
                            else:
                                valore = "N/A"
                            
                            data_info.append({
                                'Colonna': col,
                                'Stato': stato,
                                'Valore': valore
                            })
                    
                    presence_df = pd.DataFrame(data_info)
                    st.dataframe(presence_df, use_container_width=True)
                    
                    # Genera report AI usando i dati disponibili
                    st.subheader("🤖 Report AI Tecnico con Strategia Operativa")
                    
                    with st.spinner("🧠 Generazione analisi AI tecnica..."):
                        # Prepara dati per AI
                        technical_dict = df_result.iloc[0].to_dict()
                        
                        # Genera report AI
                        ai_report = generate_technical_ai_report(
                            ticker=ticker.upper(),
                            technical_dict=technical_dict
                        )
                        
                        st.markdown(escape_markdown_latex(ai_report))
                    
                    # Genera PDF
                    pdf_bytes = generate_pdf_report(
                        title=f"Analisi Tecnica - {ticker}",
                        content=ai_report,
                        filename_prefix="Technical_Report"
                    )

                    col_pdf, col_txt = st.columns(2)

                    with col_pdf:
                        st.download_button(
                            label="📥 Scarica Report PDF",
                            data=pdf_bytes,
                            file_name=f"Technical_Report_{ticker}_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                            key="download_technical_pdf_btn",
                            type="primary",
                            use_container_width=True
                        )

                    with col_txt:
                        st.download_button(
                            label="📄 Scarica TXT",
                            data=ai_report,
                            file_name=f"Technical_Report_{ticker}_{datetime.now().strftime('%Y%m%d')}.txt",
                            mime="text/plain",
                            key="download_technical_txt_btn",
                            use_container_width=True
                        )

                else:
                    st.error(f"❌ Impossibile trovare dati per il ticker **'{ticker}'**.")
                    st.info("""
                    **Suggerimenti:**
                    - Verifica che il simbolo sia corretto
                    - Per titoli italiani usa il formato: TICKER.MI (es. ENEL.MI)
                    - Per titoli USA non serve aggiungere exchange
                    - Prova a cercare il ticker su TradingView.com prima
                    """)



    # Summary
    current_date = datetime.now()
