# main.py

import streamlit as st

# Configurazione pagina DEVE essere la prima chiamata Streamlit
st.set_page_config(
    page_title="Flusso Grugno",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Importa i moduli DOPO set_page_config
try:
    from portfolio import portfolio_tracker_app
    portfolio_ok = True
except Exception as e:
    st.sidebar.error(f"Portfolio Tracker error: {e}")
    portfolio_ok = False

try:
    from transaction import transaction_tracker_app
    transaction_ok = True
except Exception as e:
    st.sidebar.error(f"Transaction tracker error: {e}")
    transaction_ok = False

try:
    from screener import stock_screener_app
    stock_ok = True
except Exception as e:
    st.sidebar.error(f"Stock Screener error: {e}")
    stock_ok = False

try:
    from decrypt import password_decryptor_app
    password_ok = True
except Exception as e:
    st.sidebar.error(f"Password Decryptor error: {e}")
    password_ok = False

# Menu di navigazione
MENU = {}

if portfolio_ok:
    MENU["📊 Portfolio Tracker"] = portfolio_tracker_app

if transaction_ok:
    MENU["💳 Transaction Tracker"] = transaction_tracker_app

if stock_ok:
    MENU["📈 Stock Screener"] = stock_screener_app

if password_ok:
    MENU["🔐 Password Decryptor"] = password_decryptor_app

if not MENU:
    st.error("❌ Nessun modulo caricato correttamente. Verifica gli errori nella sidebar.")
    st.stop()

# Sidebar
st.sidebar.title("🚀 Multi Utility App")
st.sidebar.markdown("---")

scelta = st.sidebar.radio(
    "Seleziona funzionalità:",
    list(MENU.keys())
)

st.sidebar.markdown("---")
st.sidebar.info(f"Moduli attivi: {len(MENU)}/4")

# Info aggiuntive
with st.sidebar.expander("ℹ️ Info App"):
    st.markdown("""
    ### Funzionalità disponibili:
    
    **📊 Portfolio Tracker**
    - Visualizzazione portfolio in tempo reale
    - Connessione Google Sheets
    - Statistiche e metriche            

    **💳 Transaction Tracker**
    - Caricamento dati autonomo con funzione load_sheet_csv_transactions()
    - Filtri multipli: Operazione, Strumento, Valuta, Date
    - 4 Metriche: Totale transazioni, Commissioni, Controvalore, Strumenti
    - 5 Grafici: Tipo operazione, Top strumenti, Commissioni mensili, Distribuzione valuta
    - Tabella completa con tutte le transazioni filtrate
    - Export CSV con timestamp
                
    **📈 Stock Screener**
    - Analisi titoli azionari
    - TOP 5 Picks con AI
    - Notizie tradotte (Finnhub + Google Translate)
    - Integrazione TradingView
    
    **🔐 Password Decryptor**
    - Decripta file CSV crittografati
    - Visualizzazione tabellare interattiva
    - Download dati decriptati
    
    ---
    
    **Versione:** 2.2
    
    **Sicurezza:** Tutti i dati vengono elaborati localmente
    """)

# Esegui funzionalità selezionata
MENU[scelta]()
