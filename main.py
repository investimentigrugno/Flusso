# main.py
import streamlit as st
from stock_screener_app import stock_screener_app
from password_decryptor_app import password_decryptor_app

st.set_page_config(page_title="Multi Utility App", layout="wide")

MENU = {
    "Stock Screener": stock_screener_app,
    "CSV Password Decryptor": password_decryptor_app,
    # Potrai aggiungere qui future funzionalità:
    # "Nuova Dashboard": nuova_dashboard_app,
}

st.sidebar.title("Menu")
scelta = st.sidebar.radio("Seleziona funzionalità", list(MENU.keys()))

# Qui viene eseguito il modulo scelto
MENU[scelta]()
