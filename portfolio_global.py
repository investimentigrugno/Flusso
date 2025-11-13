"""
Modulo globale per leggere e condividere i dati del Portfolio
COMPLETAMENTE ISOLATO - Non interferisce con altre funzionalità
"""

import streamlit as st
import pandas as pd
import requests
from io import StringIO
from datetime import datetime


# ==================== CONFIGURAZIONE ====================
SPREADSHEET_ID_PORTFOLIO = "1mD9jxDJv26aZwCdIbvQVjlJGBhRwKWwQnPpPPq0ON5Y"
GID_PORTFOLIO = "0"


# ==================== FUNZIONI INTERNE (NON ESPORTATE) ====================
def _parse_euro_value(value):
    """Converte un valore in formato '€ 2.228,92' in float"""
    if pd.isna(value) or value == '':
        return 0.0
    
    try:
        value_str = str(value).replace('€', '').replace(' ', '').strip()
        value_str = value_str.replace('.', '').replace(',', '.')
        return float(value_str)
    except:
        return 0.0


def _parse_percent_value(value):
    """Converte un valore in formato '6,68%' in float"""
    if pd.isna(value) or value == '':
        return 0.0
    
    try:
        value_str = str(value).replace('%', '').replace(',', '.').strip()
        return float(value_str)
    except:
        return 0.0


@st.cache_data(ttl=120, show_spinner=False)
def _load_portfolio_from_sheets():
    """
    Funzione interna per caricare i dati dal Google Sheet
    NON chiamare direttamente - usa get_portfolio_data()
    """
    try:
        url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID_PORTFOLIO}/export?format=csv&gid={GID_PORTFOLIO}"
        
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None
        
        df = pd.read_csv(StringIO(response.text), header=None)
        
        # Parsing sicuro - se il formato cambia, ritorna valori di default
        try:
            deposit = _parse_euro_value(df.iloc[1, 0])
            value_eur = _parse_euro_value(df.iloc[1, 1])
            pl_percent = _parse_percent_value(df.iloc[1, 2])
            pl_tot = _parse_euro_value(df.iloc[1, 3])
            commission_tax = _parse_euro_value(df.iloc[4, 0])
            cash_disp = _parse_euro_value(df.iloc[4, 2])
            cash_indisp = _parse_euro_value(df.iloc[4, 3])
        except:
            # Se parsing fallisce, ritorna valori nulli senza crashare
            return None
        
        return {
            'deposit': deposit,
            'value_eur': value_eur,
            'pl_percent': pl_percent,
            'pl_tot': pl_tot,
            'cash_disp': cash_disp,
            'cash_indisp': cash_indisp,
            'commission_tax': commission_tax,
            'loaded_at': datetime.now(),
            'source': 'google_sheets'
        }
        
    except Exception:
        # Qualsiasi errore ritorna None senza crashare
        return None


# ==================== FUNZIONI PUBBLICHE (SAFE) ====================

def get_portfolio_data(silent=True):
    """
    Recupera i dati del Portfolio in modo sicuro
    
    Args:
        silent (bool): Se True, non mostra errori (default)
    
    Returns:
        dict o None: Dati del portfolio o None se non disponibili
    """
    try:
        # Prova a caricare dal Google Sheet
        data = _load_portfolio_from_sheets()
        
        # Salva in session_state per accesso rapido
        if st.session_state.portfolio_data = data
            return data
        
        # Se caricamento fallisce, prova a recuperare da session_state
        if 'portfolio_data' in st.session_state:
            return st.session_state.portfolio_data
        
        return None
        
    except Exception:
        # Fallback: ritorna None senza crashare
        return None


def get_liquidita_disponibile():
    """
    Recupera solo la liquidità disponibile (CASH DISP)
    
    Returns:
        float: Liquidità disponibile o 0.0 se non disponibile
    """
    try:
        portfolio = get_portfolio_data(silent=True)
        if portfolio:
            return portfolio.get('cash_disp', 0.0)
    except:
        pass
    return 0.0


def get_liquidita_indisponibile():
    """
    Recupera la liquidità indisponibile (CASH INDISP)
    
    Returns:
        float: Liquidità indisponibile o 0.0 se non disponibile
    """
    try:
        portfolio = get_portfolio_data(silent=True)
        if portfolio:
            return portfolio.get('cash_indisp', 0.0)
    except:
        pass
    return 0.0


def get_portfolio_value():
    """
    Recupera il valore totale del portfolio (VALUE €)
    
    Returns:
        float: Valore portfolio o 0.0 se non disponibile
    """
    try:
        portfolio = get_portfolio_data(silent=True)
        if portfolio:
            return portfolio.get('value_eur', 0.0)
    except:
        pass
    return 0.0


def get_portfolio_pl_percent():
    """
    Recupera la performance percentuale (P&L %)
    
    Returns:
        float: Performance % o 0.0 se non disponibile
    """
    try:
        portfolio = get_portfolio_data(silent=True)
        if portfolio:
            return portfolio.get('pl_percent', 0.0)
    except:
        pass
    return 0.0


def get_portfolio_pl_tot():
    """
    Recupera il P&L totale in euro (P&L TOT)
    
    Returns:
        float: P&L totale o 0.0 se non disponibile
    """
    try:
        portfolio = get_portfolio_data(silent=True)
        if portfolio:
            return portfolio.get('pl_tot', 0.0)
    except:
        pass
    return 0.0


def get_portfolio_deposit():
    """
    Recupera il deposito iniziale (DEPOSIT)
    
    Returns:
        float: Deposito iniziale o 0.0 se non disponibile
    """
    try:
        portfolio = get_portfolio_data(silent=True)
        if portfolio:
            return portfolio.get('deposit', 0.0)
    except:
        pass
    return 0.0


# ==================== FUNZIONI UI OPZIONALI ====================

def display_portfolio_sidebar(show_if_unavailable=False):
    """
    Mostra un widget compatto nella sidebar (OPZIONALE)
    Se i dati non sono disponibili, non mostra nulla per non disturbare
    
    Args:
        show_if_unavailable (bool): Se True, mostra avviso se dati non disponibili
    """
    try:
        portfolio = get_portfolio_data(silent=True)
        
        if portfolio:
            st.sidebar.markdown("---")
            st.sidebar.markdown("### 💼 Portfolio")
            
            col1, col2 = st.sidebar.columns(2)
            
            with col1:
                st.metric(
                    "Valore",
                    f"€ {portfolio['value_eur']:,.2f}",
                    delta=f"{portfolio['pl_percent']:.2f}%"
                )
            
            with col2:
                st.metric(
                    "P&L",
                    f"€ {portfolio['pl_tot']:,.2f}"
                )
            
            st.sidebar.markdown("**💰 Liquidità:**")
            st.sidebar.write(f"✅ Disponibile: **€ {portfolio['cash_disp']:,.2f}**")
            st.sidebar.write(f"🔒 Indisponibile: € {portfolio['cash_indisp']:,.2f}")
            
            st.sidebar.caption(f"🕐 Aggiornato: {portfolio['loaded_at'].strftime('%H:%M:%S')}")
        elif show_if_unavailable:
            st.sidebar.info("💼 Dati Portfolio non disponibili")
    except:
        # Non mostrare nulla se c'è un errore
        pass


def display_portfolio_metrics():
    """
    Mostra metriche complete del Portfolio nel corpo della pagina (OPZIONALE)
    """
    try:
        portfolio = get_portfolio_data(silent=True)
        
        if not portfolio:
            st.warning("⚠️ Dati Portfolio non disponibili al momento")
            return
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "💼 Valore Portfolio",
                f"€ {portfolio['value_eur']:,.2f}",
                delta=f"€ {portfolio['pl_tot']:,.2f}",
                help=f"Deposit iniziale: € {portfolio['deposit']:,.2f}"
            )
        
        with col2:
            st.metric(
                "📈 Performance",
                f"{portfolio['pl_percent']:.2f}%",
                help="P&L % rispetto al deposit"
            )
        
        with col3:
            st.metric(
                "💰 Liquidità Disponibile",
                f"€ {portfolio['cash_disp']:,.2f}",
                help="Cash disponibile per nuovi ordini"
            )
        
        with col4:
            st.metric(
                "🔒 Liquidità Bloccata",
                f"€ {portfolio['cash_indisp']:,.2f}",
                help="Cash in ordini pendenti"
            )
    except:
        st.error("❌ Errore nel caricamento delle metriche Portfolio")


def refresh_portfolio_data():
    """
    Forza il refresh dei dati del Portfolio
    Da usare insieme a st.cache_data.clear() se necessario
    """
    try:
        _load_portfolio_from_sheets.clear()
        return get_portfolio_data(silent=True)
    except:
        return None


# ==================== FUNZIONE DI TEST ====================

def test_portfolio_connection():
    """
    Testa la connessione al foglio Portfolio
    Returns (bool, str): (successo, messaggio)
    """
    try:
        portfolio = _load_portfolio_from_sheets()
        if portfolio:
            return True, f"✅ Connessione OK - Liquidità: € {portfolio['cash_disp']:,.2f}"
        else:
            return False, "❌ Impossibile caricare i dati dal foglio Portfolio"
    except Exception as e:
        return False, f"❌ Errore: {str(e)}"
