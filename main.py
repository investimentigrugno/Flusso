# main.py
import streamlit as st
from stock_screener import stock_screener_app
from encrypt_decrypt_password_csv import password_decryptor_app

# Configurazione pagina principale
st.set_page_config(
    page_title="Multi Utility App",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Menu di navigazione
MENU = {
    "📈 Stock Screener": stock_screener_app,
    "🔐 Password Decryptor": password_decryptor_app,
    # Aggiungi qui altre funzionalità future:
    # "📊 Nuova Dashboard": nuova_dashboard_app,
    # "💰 Crypto Tracker": crypto_tracker_app,
}

# Sidebar per il menu
st.sidebar.title("🚀 Multi Utility App")
st.sidebar.markdown("---")
st.sidebar.markdown("### 📍 Navigazione")

# Radio button per selezionare la funzionalità
scelta = st.sidebar.radio(
    "Seleziona funzionalità:",
    list(MENU.keys()),
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.markdown("""
### ℹ️ Informazioni App

**Funzionalità disponibili:**

- 📈 **Stock Screener**: Analisi mercati finanziari con AI
- 🔐 **Password Decryptor**: Decripta CSV crittografati

**Versione:** 1.0.0  
**Sviluppato con:** Streamlit + Python
""")

# Esegui la funzionalità selezionata
MENU[scelta]()
