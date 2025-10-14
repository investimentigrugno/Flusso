# encrypt_decrypt_password_csv.py
import streamlit as st
import hashlib
import base64
import pandas as pd
from io import StringIO
import os

def decrypt_data(encrypted_data, key):
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
        raise Exception('Decriptazione fallita.')

def xor_decrypt(encrypted, key):
    decoded = base64.b64decode(encrypted).decode('utf-8')
    result = []
    for i, char in enumerate(decoded):
        key_char = ord(key[i % len(key)])
        enc_char = ord(char)
        result.append(chr(enc_char ^ key_char))
    return ''.join(result)

def password_decryptor_app():
    st.title("🔐 CSV Password Decryptor")
    st.markdown("Decripta i tuoi file CSV di credenziali")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📁 Carica File")
        uploaded_file = st.file_uploader("Seleziona CSV crittografato:", type=['csv'])
        
        if uploaded_file:
            file_content = uploaded_file.read().decode('utf-8').strip()
            st.success(f"File caricato: {uploaded_file.name}")
            st.info(f"Dimensione: {len(file_content)} caratteri")
    
    with col2:
        st.header("🔑 Chiave Master")
        master_key = st.text_input("Inserisci chiave master:", type="password", placeholder="Min 8 caratteri")
        
        if master_key:
            if len(master_key) < 8:
                st.error("Chiave troppo corta!")
            else:
                st.success(f"Chiave OK ({len(master_key)} caratteri)")
    
    if uploaded_file and master_key and len(master_key) >= 8:
        st.header("🔓 Decriptazione")
        
        try:
            with st.spinner("Decriptazione in corso..."):
                decrypted_csv = decrypt_data(file_content, master_key)
                st.success("Decriptazione riuscita!")
                
                # Parsing CSV
                lines = decrypted_csv.strip().split('\n')
                if lines:
                    # Prima riga = headers
                    headers = lines[0].split(',')
                    
                    # Resto = dati
                    data_rows = []
                    for line in lines[1:]:
                        if line.strip():
                            row = line.split(',')
                            data_rows.append(row)
                    
                    if data_rows:
                        # Crea DataFrame
                        df = pd.DataFrame(data_rows, columns=headers)
                        
                        # Tab per diverse visualizzazioni
                        tab1, tab2, tab3 = st.tabs(["📊 Tabella", "📋 CSV Grezzo", "💾 Download"])
                        
                        with tab1:
                            st.subheader(f"Credenziali Trovate: {len(df)}")
                            
                            # Opzione nascondi password
                            hide_passwords = st.checkbox("🙈 Nascondi password", value=True)
                            display_df = df.copy()
                            
                            if hide_passwords and 'PASSWORD' in display_df.columns:
                                display_df['PASSWORD'] = display_df['PASSWORD'].apply(
                                    lambda x: '*' * min(len(str(x)), 8) if pd.notna(x) else ''
                                )
                            
                            # Mostra tabella
                            st.dataframe(display_df, use_container_width=True, height=400)
                            
                            # Statistiche
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Totale credenziali", len(df))
                            with col2:
                                st.metric("Colonne", len(df.columns))
                            with col3:
                                filled_passwords = len(df[df.iloc[:, 2].notna()]) if len(df.columns) > 2 else 0
                                st.metric("Password non vuote", filled_passwords)
                        
                        with tab2:
                            st.subheader("Dati CSV Completi")
                            st.text_area("Contenuto CSV:", decrypted_csv, height=300)
                        
                        with tab3:
                            st.subheader("Scarica File Decriptato")
                            timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"credenziali_decriptate_{timestamp}.csv"
                            
                            st.download_button(
                                label="📥 Scarica CSV Decriptato",
                                data=decrypted_csv,
                                file_name=filename,
                                mime='text/csv'
                            )
                            st.warning("⚠️ Il file conterrà credenziali in chiaro!")
                    else:
                        st.warning("Nessun dato trovato nel CSV")
                else:
                    st.error("File CSV vuoto")
        
        except Exception as e:
            st.error(f"Errore decriptazione: {str(e)}")
            st.info("Verifica che la chiave sia corretta")
    
    st.markdown("---")
    st.markdown("**CSV Password Decryptor** • Sicuro • Privato")
