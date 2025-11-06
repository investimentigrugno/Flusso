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

# ============================================================================
# 1. FETCH TUTTE LE METRICHE FONDAMENTALI COMPLETE
# ============================================================================

def fetch_comprehensive_fundamentals(ticker_symbol):
    """
    Recupera TUTTE le metriche fondamentali necessarie per analisi DCF
    """
    try:
        stock = yf.Ticker(ticker_symbol)

        # Info generiche
        info = stock.info

        # Bilancio, conto economico, cash flow
        balance_sheet = stock.balance_sheet  # Annuale
        q_balance = stock.quarterly_balance_sheet  # Trimestrale
        income_stmt = stock.income_stmt  # Annuale
        q_income = stock.quarterly_income_stmt  # Trimestrale
        cashflow = stock.cashflow  # Annuale
        q_cashflow = stock.quarterly_cashflow  # Trimestrale

        return {
            'info': info,
            'balance_sheet': balance_sheet,
            'quarterly_balance': q_balance,
            'income_stmt': income_stmt,
            'quarterly_income': q_income,
            'cashflow': cashflow,
            'quarterly_cashflow': q_cashflow,
            'ticker': stock
        }
    except Exception as e:
        print(f"❌ Errore fetch dati: {e}")
        return None

# ============================================================================
# 2. ESTRAZIONE METRICHE FONDAMENTALI CHIAVE
# ============================================================================

def extract_fundamental_metrics(data) -> Dict:
    """
    Estrae tutte le metriche fondamentali da yfinance
    Per analisi completa e DCF
    """

    info = data['info']
    income_stmt = data['income_stmt']
    cashflow = data['cashflow']
    balance = data['balance_sheet']

    # Metriche di base
    metrics = {
        # ========== METRICHE DI VALUTAZIONE ==========
        'P/E Ratio Trailing': info.get('trailingPE'),
        'P/E Ratio Forward': info.get('forwardPE'),
        'PEG Ratio': info.get('pegRatio'),
        'Price/Book': info.get('priceToBook'),
        'Price/Sales': info.get('priceToSalesTrailing12Months'),

        # ========== CRESCITA ==========
        'Revenue Growth': info.get('revenueGrowth'),
        'Earnings Growth': info.get('earningsGrowth'),
        'Revenue (TTM)': info.get('totalRevenue'),
        'Earnings (TTM)': info.get('netIncomeToCommon'),

        # ========== REDDITIVITÀ ==========
        'Profit Margin': info.get('profitMargins'),
        'Operating Margin': info.get('operatingMargins'),
        'Gross Margin': info.get('grossMargins'),
        'ROE': info.get('returnOnEquity'),
        'ROA': info.get('returnOnAssets'),
        'EBITDA': info.get('ebitda'),
        'Operating Income': info.get('operatingIncome'),

        # ========== LIQUIDITÀ E CAPITALE CIRCOLANTE ==========
        'Current Ratio': info.get('currentRatio'),
        'Quick Ratio': info.get('quickRatio'),
        'Cash': info.get('totalCash'),
        'Working Capital': info.get('workingCapital'),

        # ========== DEBITO E SOLVIBILITÀ ==========
        'Total Debt': info.get('totalDebt'),
        'Debt/Equity': info.get('debtToEquity'),
        'Long-term Debt': info.get('longTermDebt'),
        'Net Debt': info.get('netDebt'),

        # ========== FLUSSI DI CASSA ==========
        'Free Cash Flow': info.get('freeCashflow'),
        'Operating Cash Flow': info.get('operatingCashflow'),
        'FCF Margin': info.get('freeCashflow') / info.get('totalRevenue', 1) if info.get('totalRevenue') else None,

        # ========== VALUTAZIONE ENTERPRISE ==========
        'Enterprise Value': info.get('enterpriseValue'),
        'EV/Revenue': info.get('enterpriseToRevenue'),
        'EV/EBITDA': info.get('enterpriseToEbitda'),

        # ========== DIVIDENDI ==========
        'Dividend Yield': info.get('dividendYield'),
        'Payout Ratio': info.get('payoutRatio'),
        'Dividend Rate': info.get('dividendRate'),

        # ========== MARKET ==========
        'Market Cap': info.get('marketCap'),
        'Shares Outstanding': info.get('sharesOutstanding'),
        'Beta': info.get('beta'),

        # ========== ANALISTI ==========
        'Target Mean Price': info.get('targetMeanPrice'),
        'Number of Analysts': info.get('numberOfAnalysts'),
        'Recommendation Key': info.get('recommendationKey'),

        # ========== ALTRO ==========
        'Industry': info.get('industry'),
        'Sector': info.get('sector'),
        'Country': info.get('country'),
        'Currency': info.get('currency'),
    }

    return metrics

# ============================================================================
# 3. CALCOLO WACC (Weighted Average Cost of Capital)
# ============================================================================

def calculate_wacc(data, risk_free_rate=0.045, market_risk_premium=0.065) -> float:
    """
    Calcola WACC (Weighted Average Cost of Capital)
    Per usare come discount rate nel DCF

    Formula: WACC = (E/V × Re) + (D/V × Rd × (1 - Tc))

    Dove:
    - E = Market Value of Equity
    - D = Market Value of Debt
    - V = E + D
    - Re = Cost of Equity (usando CAPM: Rf + β(Rm - Rf))
    - Rd = Cost of Debt
    - Tc = Corporate Tax Rate
    """

    info = data['info']
    income = data['income_stmt']

    try:
        # 1. Calcola Cost of Equity (CAPM)
        beta = info.get('beta', 1.0)
        cost_of_equity = risk_free_rate + beta * market_risk_premium  # CAPM formula

        # 2. Market Value di Equity
        market_cap = info.get('marketCap', 1)

        # 3. Market Value di Debt (approssimativamente Total Debt)
        total_debt = info.get('totalDebt', 0)

        # 4. Cost of Debt
        interest_expense = income.iloc[0]['Interest Expense'] if 'Interest Expense' in income.index else 0
        cost_of_debt = interest_expense / max(total_debt, 1)

        # 5. Tax Rate
        tax_expense = income.iloc[0]['Income Tax Expense'] if 'Income Tax Expense' in income.index else 0
        total_income_before_tax = interest_expense + (income.iloc[0]['Net Income'] + tax_expense)
        tax_rate = tax_expense / max(total_income_before_tax, 1)

        # 6. Total Value
        total_value = market_cap + total_debt

        # 7. WACC
        if total_value > 0:
            wacc = (market_cap / total_value * cost_of_equity) +                    (total_debt / total_value * cost_of_debt * (1 - tax_rate))
            return wacc
        else:
            return cost_of_equity

    except Exception as e:
        print(f"❌ Errore calcolo WACC: {e}")
        return 0.10  # Default 10%

# ============================================================================
# 4. ANALISI FLUSSI DI CASSA
# ============================================================================

def analyze_cash_flows(data) -> Dict:
    """
    Analizza i flussi di cassa storici per proiezioni future
    """

    try:
        cashflow = data['cashflow']

        # Estrai dati ultimi 5 anni (o quanti disponibili)
        periods = min(5, len(cashflow.columns))

        cf_data = {
            'Operating Cash Flow': [],
            'Free Cash Flow': [],
            'Capital Expenditures': [],
            'Dividends Paid': [],
            'Debt Repayment': []
        }

        for i in range(periods):
            try:
                # Operating Cash Flow
                ocf = cashflow.iloc[0, i] if len(cashflow) > 0 else 0
                cf_data['Operating Cash Flow'].append(ocf)

                # Capital Expenditures (di solito riga 1)
                capex = cashflow.iloc[1, i] if len(cashflow) > 1 else 0
                cf_data['Capital Expenditures'].append(capex)

                # Free Cash Flow = OCF - CapEx
                fcf = ocf + capex  # CapEx è negativo
                cf_data['Free Cash Flow'].append(fcf)

                # Dividends Paid
                divs = cashflow.iloc[3, i] if len(cashflow) > 3 else 0
                cf_data['Dividends Paid'].append(divs)

                # Debt Repayment
                debt_rep = cashflow.iloc[5, i] if len(cashflow) > 5 else 0
                cf_data['Debt Repayment'].append(debt_rep)

            except:
                pass

        # Calcola trend e tasso di crescita
        if len(cf_data['Free Cash Flow']) > 1:
            fcf_list = [x for x in cf_data['Free Cash Flow'] if x != 0]
            if len(fcf_list) > 1:
                fcf_growth = (fcf_list[-1] / fcf_list[0]) ** (1 / (len(fcf_list) - 1)) - 1
            else:
                fcf_growth = 0
        else:
            fcf_growth = 0

        return {
            'historical_data': cf_data,
            'average_fcf': np.mean([x for x in cf_data['Free Cash Flow'] if x != 0]) if cf_data['Free Cash Flow'] else 0,
            'average_ocf': np.mean([x for x in cf_data['Operating Cash Flow'] if x != 0]) if cf_data['Operating Cash Flow'] else 0,
            'average_capex': np.mean([abs(x) for x in cf_data['Capital Expenditures'] if x != 0]) if cf_data['Capital Expenditures'] else 0,
            'fcf_growth_rate': fcf_growth,
            'periods_available': periods
        }

    except Exception as e:
        print(f"❌ Errore analisi cash flow: {e}")
        return {}

# ============================================================================
# 5. MODELLO DCF (Discounted Cash Flow)
# ============================================================================

def calculate_dcf_value(data, wacc: float, 
                       forecast_years: int = 5,
                       terminal_growth_rate: float = 0.025) -> Dict:
    """
    Calcola il valore intrinseco usando DCF

    Passi:
    1. Proietta Free Cash Flow futuri (5 anni)
    2. Calcola Terminal Value
    3. Sconta tutti i CF al presente usando WACC
    4. Calcola valore per azione
    """

    try:
        info = data['info']
        cashflow_analysis = analyze_cash_flows(data)

        if not cashflow_analysis or not cashflow_analysis.get('average_fcf'):
            return None

        # 1. FCF Base (ultimo anno o media)
        base_fcf = cashflow_analysis['average_fcf']
        fcf_growth = cashflow_analysis['fcf_growth_rate']

        # 2. Proietta FCF per i prossimi forecast_years
        projected_fcf = []
        for year in range(1, forecast_years + 1):
            fcf = base_fcf * ((1 + fcf_growth) ** year)
            projected_fcf.append(fcf)

        # 3. Calcola Terminal Value (usando Gordon Growth Model)
        terminal_fcf = projected_fcf[-1] * (1 + terminal_growth_rate)
        terminal_value = terminal_fcf / (wacc - terminal_growth_rate)

        # 4. Sconta al presente
        pv_fcf = []
        for year, fcf in enumerate(projected_fcf, 1):
            pv = fcf / ((1 + wacc) ** year)
            pv_fcf.append(pv)

        # 5. Sconta Terminal Value
        pv_terminal = terminal_value / ((1 + wacc) ** forecast_years)

        # 6. Enterprise Value
        enterprise_value = sum(pv_fcf) + pv_terminal

        # 7. Equity Value = Enterprise Value - Net Debt
        net_debt = info.get('totalDebt', 0) - info.get('totalCash', 0)
        equity_value = enterprise_value - net_debt

        # 8. Valore per azione
        shares_out = info.get('sharesOutstanding', 1)
        value_per_share = equity_value / shares_out

        # 9. Current Price
        current_price = info.get('currentPrice', 1)
        upside_downside = ((value_per_share / current_price) - 1) * 100

        return {
            'base_fcf': base_fcf,
            'fcf_growth_rate': fcf_growth,
            'projected_fcf': projected_fcf,
            'terminal_fcf': terminal_fcf,
            'terminal_value': terminal_value,
            'pv_fcf': pv_fcf,
            'pv_terminal': pv_terminal,
            'enterprise_value': enterprise_value,
            'net_debt': net_debt,
            'equity_value': equity_value,
            'value_per_share': value_per_share,
            'current_price': current_price,
            'upside_downside': upside_downside,
            'recommendation': 'BUY' if upside_downside > 15 else 'HOLD' if upside_downside > -15 else 'SELL',
            'confidence': min(abs(upside_downside) / 50, 1.0)  # 0-1
        }

    except Exception as e:
        print(f"❌ Errore DCF: {e}")
        return None

# ============================================================================
# 6. ANALISI QUALITATIVA FONDAMENTALE
# ============================================================================

def qualitative_fundamental_analysis(metrics: Dict) -> Dict:
    """
    Analisi qualitativa basata su metriche fondamentali
    """

    analysis = {
        'valuation_score': 0.5,
        'growth_score': 0.5,
        'profitability_score': 0.5,
        'financial_health_score': 0.5,
        'overall_score': 0.5,
        'comments': []
    }

    # 1. VALUTAZIONE
    pe = metrics.get('P/E Ratio Trailing')
    pb = metrics.get('Price/Book')
    peg = metrics.get('PEG Ratio')

    if pe and pe > 0:
        if pe < 15:
            analysis['valuation_score'] = 0.8
            analysis['comments'].append("✅ P/E basso: azione potenzialmente sottovalutata")
        elif pe > 30:
            analysis['valuation_score'] = 0.2
            analysis['comments'].append("⚠️ P/E alto: azione potenzialmente sopravvalutata")
        else:
            analysis['valuation_score'] = 0.5

    if peg and peg > 0:
        if peg < 1.0:
            analysis['valuation_score'] = max(analysis['valuation_score'], 0.7)
            analysis['comments'].append("✅ PEG < 1.0: buon rapporto prezzo/crescita")

    # 2. CRESCITA
    rev_growth = metrics.get('Revenue Growth')
    eps_growth = metrics.get('Earnings Growth')

    if rev_growth and rev_growth > 0.10:
        analysis['growth_score'] = 0.8
        analysis['comments'].append(f"✅ Crescita ricavi forte: {rev_growth*100:.1f}%")
    elif rev_growth and rev_growth < 0:
        analysis['growth_score'] = 0.2
        analysis['comments'].append(f"⚠️ Calo ricavi: {rev_growth*100:.1f}%")

    if eps_growth and eps_growth > 0.15:
        analysis['growth_score'] = max(analysis['growth_score'], 0.8)
        analysis['comments'].append(f"✅ Crescita EPS forte: {eps_growth*100:.1f}%")

    # 3. REDDITIVITÀ
    margin = metrics.get('Profit Margin')
    roe = metrics.get('ROE')

    if margin and margin > 0.15:
        analysis['profitability_score'] = 0.8
        analysis['comments'].append(f"✅ Margine profitti alto: {margin*100:.1f}%")
    elif margin and margin < 0:
        analysis['profitability_score'] = 0.2
        analysis['comments'].append(f"⚠️ Margine negativo: {margin*100:.1f}%")

    if roe and roe > 0.15:
        analysis['profitability_score'] = max(analysis['profitability_score'], 0.8)
        analysis['comments'].append(f"✅ ROE eccellente: {roe*100:.1f}%")

    # 4. SALUTE FINANZIARIA
    debt_eq = metrics.get('Debt/Equity')
    current_ratio = metrics.get('Current Ratio')

    if debt_eq and debt_eq < 0.5:
        analysis['financial_health_score'] = 0.8
        analysis['comments'].append(f"✅ Leva finanziaria bassa: {debt_eq:.2f}")
    elif debt_eq and debt_eq > 2.0:
        analysis['financial_health_score'] = 0.2
        analysis['comments'].append(f"⚠️ Leva finanziaria alta: {debt_eq:.2f}")

    if current_ratio and current_ratio > 1.5:
        analysis['financial_health_score'] = max(analysis['financial_health_score'], 0.8)
        analysis['comments'].append(f"✅ Liquidità buona: Ratio {current_ratio:.2f}")
    elif current_ratio and current_ratio < 1.0:
        analysis['financial_health_score'] = min(analysis['financial_health_score'], 0.3)
        analysis['comments'].append(f"⚠️ Liquidità critica: Ratio {current_ratio:.2f}")

    # 5. SCORE FINALE
    analysis['overall_score'] = np.mean([
        analysis['valuation_score'],
        analysis['growth_score'],
        analysis['profitability_score'],
        analysis['financial_health_score']
    ])

    # Rating
    if analysis['overall_score'] >= 0.75:
        analysis['rating'] = '🟢 STRONG BUY'
    elif analysis['overall_score'] >= 0.60:
        analysis['rating'] = '🟢 BUY'
    elif analysis['overall_score'] >= 0.40:
        analysis['rating'] = '🟡 HOLD'
    else:
        analysis['rating'] = '🔴 SELL'

    return analysis

# ============================================================================
# 7. FUNZIONE PRINCIPALE: ANALISI FONDAMENTALE COMPLETA
# ============================================================================

def comprehensive_fundamental_analysis(ticker_symbol: str) -> Dict:
    """
    Esegue analisi fondamentale COMPLETA con:
    - Tutte le metriche chiave
    - Cash flow analysis
    - DCF valuation
    - Qualitative scoring
    """

    print(f"\n📊 ANALISI FONDAMENTALE COMPLETA: {ticker_symbol.upper()}")
    print("=" * 70)

    # 1. Fetch dati
    print("\n1️⃣ Recupero dati..."  )
    data = fetch_comprehensive_fundamentals(ticker_symbol)

    if not data:
        return None

    # 2. Estrai metriche
    print("2️⃣ Estrazione metriche...")
    metrics = extract_fundamental_metrics(data)

    # 3. Calcola WACC
    print("3️⃣ Calcolo WACC...")
    wacc = calculate_wacc(data)

    # 4. Analisi Cash Flow
    print("4️⃣ Analisi flussi di cassa...")
    cf_analysis = analyze_cash_flows(data)

    # 5. DCF Valuation
    print("5️⃣ Valutazione DCF...")
    dcf_result = calculate_dcf_value(data, wacc)

    # 6. Analisi Qualitativa
    print("6️⃣ Analisi qualitativa...")
    qual_analysis = qualitative_fundamental_analysis(metrics)

    # 7. Risultato finale
    result = {
        'ticker': ticker_symbol.upper(),
        'timestamp': datetime.now().isoformat(),
        'metrics': metrics,
        'wacc': wacc,
        'cash_flow_analysis': cf_analysis,
        'dcf_valuation': dcf_result,
        'qualitative_analysis': qual_analysis,
    }

    return result

# ============================================================================
# 8. DISPLAY FORMATTATO RISULTATI
# ============================================================================

def print_fundamental_analysis(result: Dict):
    """
    Stampa risultati in formato leggibile
    """

    if not result:
        print("❌ Analisi non disponibile")
        return

    ticker = result['ticker']
    metrics = result['metrics']
    dcf = result['dcf_valuation']
    qual = result['qualitative_analysis']

    print(f"\n\n📊 ANALISI FONDAMENTALE COMPLETA: {ticker}")
    print("=" * 70)

    # Metriche di Valutazione
    print("\n📈 METRICHE DI VALUTAZIONE:")
    print(f"  P/E Trailing: {metrics.get('P/E Ratio Trailing', 'N/A')}")
    print(f"  P/E Forward: {metrics.get('P/E Ratio Forward', 'N/A')}")
    print(f"  PEG Ratio: {metrics.get('PEG Ratio', 'N/A')}")
    print(f"  Price/Book: {metrics.get('Price/Book', 'N/A')}")

    # Crescita
    print("\n📊 CRESCITA:")
    print(f"  Revenue Growth: {metrics.get('Revenue Growth', 'N/A')}")
    print(f"  Earnings Growth: {metrics.get('Earnings Growth', 'N/A')}")

    # Redditività
    print("\n💰 REDDITIVITÀ:")
    print(f"  Profit Margin: {metrics.get('Profit Margin', 'N/A')}")
    print(f"  ROE: {metrics.get('ROE', 'N/A')}")
    print(f"  ROA: {metrics.get('ROA', 'N/A')}")

    # Flussi di Cassa
    print("\n💵 FLUSSI DI CASSA:")
    print(f"  Free Cash Flow: {metrics.get('Free Cash Flow', 'N/A')}")
    print(f"  Operating Cash Flow: {metrics.get('Operating Cash Flow', 'N/A')}")
    print(f"  FCF Growth: {result['cash_flow_analysis'].get('fcf_growth_rate', 'N/A')}")

    # DCF
    if dcf:
        print("\n🎯 VALUTAZIONE DCF:")
        print(f"  Enterprise Value: ${dcf.get('enterprise_value', 0):.2e}")
        print(f"  Equity Value: ${dcf.get('equity_value', 0):.2e}")
        print(f"  Value per Share: ${dcf.get('value_per_share', 0):.2f}")
        print(f"  Current Price: ${dcf.get('current_price', 0):.2f}")
        print(f"  Upside/Downside: {dcf.get('upside_downside', 0):.1f}%")
        print(f"  DCF Raccomandazione: {dcf.get('recommendation', 'HOLD')}")

    # Analisi Qualitativa
    print("\n📊 ANALISI QUALITATIVA:")
    print(f"  Rating: {qual.get('rating', 'N/A')}")
    print(f"  Overall Score: {qual.get('overall_score', 0):.2f}/1.0")
    print(f"  Valuation Score: {qual.get('valuation_score', 0):.2f}")
    print(f"  Growth Score: {qual.get('growth_score', 0):.2f}")
    print(f"  Profitability Score: {qual.get('profitability_score', 0):.2f}")
    print(f"  Financial Health: {qual.get('financial_health_score', 0):.2f}")

    print("\n📝 COMMENTI:")
    for comment in qual.get('comments', []):
        print(f"  {comment}")

    print("\n" + "=" * 70)

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
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "🎯 Top Picks", "🔍 TradingView Search"])
    
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
                    st.markdown("")
                    analyze_btn = st.button(
                        "📊 Analizza", 
                        key="analyze_fundamentals_btn",
                        type="primary",
                        use_container_width=True
                    )
                
                # Esempi rapidi
                st.markdown("**📈 Esempi rapidi:**")
                col_ex1, col_ex2, col_ex3, col_ex4 = st.columns(4)
                
                examples = [
                    ("🍎 NASDAQ:AAPL", "NASDAQ:AAPL"),
                    ("🚗 NASDAQ:TSLA", "NASDAQ:TSLA"),
                    ("🏢 NYSE:JPM", "NYSE:JPM"),
                    ("🇮🇹 MIL:ENEL", "MIL:ENEL")
                ]
                
                for i, (label, ticker_val) in enumerate(examples):
                    with [col_ex1, col_ex2, col_ex3, col_ex4][i]:
                        if st.button(label, key=f"ex_{i}", use_container_width=True):
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


            # Summary
            current_date = datetime.now()
