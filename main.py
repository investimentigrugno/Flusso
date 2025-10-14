# main.py

import streamlit as st

# Configurazione pagina DEVE essere la prima chiamata Streamlit
st.set_page_config(
    page_title="Multi Utility App",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Importa i moduli DOPO set_page_config
try:
    from stock_screener import stock_screener_app
    stock_ok = True
except Exception as e:
    st.sidebar.error(f"Stock Screener error: {e}")
    stock_ok = False

try:
    from encrypt_decrypt_password_csv import password_decryptor_app, password_encryptor_app
    password_ok = True
except Exception as e:
    st.sidebar.error(f"Password tools error: {e}")
    password_ok = False

# Menu di navigazione
MENU = {}

if stock_ok:
    MENU["📈 Stock Screener"] = stock_screener_app

if password_ok:
    MENU["🔒 Password Encryptor"] = password_encryptor_app
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
st.sidebar.info(f"Moduli attivi: {len(MENU)}/3")

# Info aggiuntive
with st.sidebar.expander("ℹ️ Info App"):
    st.markdown("""
    ### Funzionalità disponibili:
    
    **📈 Stock Screener**
    - Analisi titoli azionari
    
    **🔒 Password Encryptor**
    - Cripta file CSV con credenziali
    
    **🔐 Password Decryptor**
    - Decripta file CSV crittografati
    
    ---
    
    **Versione:** 2.0
    
    **Sicurezza:** Tutti i dati vengono elaborati localmente
    """)

# Esegui funzionalità selezionata
MENU[scelta]()
