# main.py (alternativa con __import__)
import streamlit as st

st.set_page_config(
    page_title="Multi Utility App",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Importa usando __import__ (supporta trattini)
stock_screener_module = __import__("stock_screener")
password_module = __import__("encrypt_decrypt_password_csv")

# Estrai le funzioni
stock_screener_app = stock_screener_module.stock_screener_app
password_decryptor_app = password_module.password_decryptor_app

# Menu di navigazione
MENU = {
    "📈 Stock Screener": stock_screener_app,
    "🔐 Password Decryptor": password_decryptor_app,
}

# Sidebar per il menu
st.sidebar.title("🚀 Multi Utility App")
st.sidebar.markdown("---")
st.sidebar.markdown("### 📍 Navigazione")

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

MENU[scelta]()
