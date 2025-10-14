# encrypt_decrypt_password_csv.py
import streamlit as st
import hashlib
import base64
import uuid
import pandas as pd
from io import StringIO
import os

def decrypt_data(encrypted_data, key):
    """Decripta i dati usando la chiave master"""
    try:
        decoded = base64.b64decode(encrypted_data).decode('utf-8')
        parts = decoded.split('::')
        if len(parts) != 2:
            raise Exception('Formato dati non valido')
        salt = parts[0]
        encrypted = parts[1]
        derived_key = hashlib.sha256((key + salt).encode('utf-8')).digest()
        key_base64 = base64.b64encode(derived_key).decode('utf-8')
        return xor_decrypt(encrypted, key_base64)
    except Exception as e:
        raise Exception('Decriptazione fallita. Chiave errata o file corrotto.')

def xor_decrypt(encrypted, key):
    """Decriptografia XOR"""
    decoded = base64.b64decode(encrypted).decode('utf-8')
    result = []
    for i, char in enumerate(decoded):
        key_char = ord(key[i % len(key)])
        enc_char = ord(char)
        result.append(chr(enc_char ^ key_char))
    return ''.join(result)

def parse_csv_row(row):
    """Parse CSV row gestendo virgolette e virgole"""
    cells = []
    cell = ''
    in_quotes = False
    i = 0
    
    while i < len(row):
        char = row[i]
        next_char = row[i + 1] if i + 1 < len(row) else ''
        
        if char == '"':
            if in_quotes and next_char == '"':
                cell += '"'
                i += 1
            else:
                in_quotes = not in_quotes
        elif char == ',' and not in_quotes:
            cells.append(cell)
            cell = ''
        else:
            cell += char
        
        i += 1
    
    cells.append(cell)
    return cells

def password_decryptor_app():
    """Funzione principale dell'app"""
    
    st.title("🔐 CSV Password Decryptor")
    st.markdown("**Decripta in sicurezza i tuoi file CSV di credenziali crittografati**")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📁 Carica File Crittografato")
        uploaded_file = st.file_uploader(
            "Seleziona il file CSV crittografato:",
            type=['csv'],
            help="Carica il file .csv generato dal Google Apps Script Password Manager"
        )
        
        if uploaded_file is not None:
            file_content = uploaded_file.read().decode('utf-8').strip()
            st.success(f"✅ File caricato: **{uploaded_file.name}**")
            st.info(f"📊 Dimensione: {len(file_content)} caratteri")
    
    with col2:
        st.header("🔑 Chiave Master")
        master_key = st.text_input(
            "Inserisci la chiave master:",
            type="password",
            help="La stessa chiave usata per crittografare i dati",
            placeholder="Minimum 8 caratteri..."
        )
        
        if master_key:
            if len(master_key) < 8:
                st.error("❌ La chiave deve essere almeno 8 caratteri!")
            else:
                st.success(f"✅ Chiave inserita ({len(master_key)} caratteri)")
    
    if uploaded_file is not None and master_key and len(master_key) >= 8:
        st.header("🔓 Decriptazione")
        
        try:
            with st.spinner("🔄 Decriptazione in corso..."):
                decrypted_csv = decrypt_data(file_content, master_key)
                rows = decrypted_csv.split('\n')
                data = [parse_csv_row(row) for row in rows if row.strip()]
                
                if data and len(data) > 1:
                    df = pd.DataFrame(data[1:], columns=data[0])
                    st.success(f"✅ **Decriptazione riuscita!** Trovate {len(df)} credenziali")
                    
                    tab1, tab2, tab3 = st.tabs(["📊 Tabella Interattiva", "📋 CSV Grezzo", "💾 Download"])
                    
                    with tab1:
                        st.subheader("🔎 Credenziali Decriptate - Tabella Interattiva")
                        st.info("👇 Questa è una tabella interattiva Pandas - puoi ordinare, cercare e scorrere")
                        
                        hide_passwords = st.checkbox("🙈 Nascondi password", value=True)
                        
                        display_df = df.copy()
                        if hide_passwords:
                            password_cols = [col for col in display_df.columns if 'PASSWORD' in col.upper()]
                            for col in password_cols:
                                display_df[col] = display_df[col].apply(
                                    lambda x: '********' if pd.notna(x) and str(x).strip() else ''
                                )
                        
                        st.dataframe(
                            display_df,
                            use_container_width=True,
                            height=500
                        )
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("📊 Totale credenziali", len(df))
                        with col2:
                            st.metric("📋 Colonne", len(df.columns))
                        with col3:
                            password_col = [c for c in df.columns if 'PASSWORD' in c.upper()]
                            if password_col:
                                filled = len(df[df[password_col[0]].notna() & (df[password_col[0]] != '')])
                                st.metric("🔑 Password compilate", filled)
                    
                    with tab2:
                        st.subheader("📋 Dati CSV in formato testo")
                        st.info("👇 Questo è il CSV grezzo in formato testuale (non interattivo)")
                        st.text_area(
                            "Contenuto CSV completo:",
                            decrypted_csv,
                            height=400,
                            help="Dati CSV in formato testuale grezzo"
                        )
                    
                    with tab3:
                        st.subheader("💾 Scarica File Decriptato")
                        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
                        download_filename = f"credenziali_decriptate_{timestamp}.csv"
                        
                        st.download_button(
                            label="📥 Scarica CSV Decriptato",
                            data=decrypted_csv,
                            file_name=download_filename,
                            mime='text/csv',
                            help="Scarica il file CSV con i dati in chiaro"
                        )
                        
                        st.warning("⚠️ **ATTENZIONE SICUREZZA:** Il file scaricato conterrà le credenziali in chiaro!")
                else:
                    st.error("❌ Nessun dato trovato nel file decriptato")
        
        except Exception as e:
            st.error(f"❌ **Errore durante la decriptazione:** {str(e)}")
            st.info("**Possibili cause:** Chiave master errata, File corrotto o non valido")
    
    st.markdown("---")
    st.markdown("**CSV Password Decryptor** | Sicuro • Privato • Open Source")
