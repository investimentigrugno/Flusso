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
        raise Exception('Decriptazione fallita. Chiave errata o file corrotto.')

def xor_decrypt(encrypted, key):
    decoded = base64.b64decode(encrypted).decode('utf-8')
    result = []
    for i, char in enumerate(decoded):
        key_char = ord(key[i % len(key)])
        enc_char = ord(char)
        result.append(chr(enc_char ^ key_char))
    return ''.join(result)

def parse_csv_row(row):
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
    st.title("CSV Password Decryptor")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Carica File")
        uploaded_file = st.file_uploader("CSV crittografato:", type=['csv'])
        if uploaded_file:
            file_content = uploaded_file.read().decode('utf-8').strip()
            st.success("File caricato")
    
    with col2:
        st.subheader("Chiave Master")
        master_key = st.text_input("Inserisci chiave:", type="password")
        if master_key and len(master_key) >= 8:
            st.success("Chiave OK")
    
    if uploaded_file and master_key and len(master_key) >= 8:
        st.subheader("Decriptazione")
        try:
            decrypted_csv = decrypt_data(file_content, master_key)
            rows = decrypted_csv.split('\n')
            data = [parse_csv_row(row) for row in rows if row.strip()]
            
            if len(data) > 1:
                df = pd.DataFrame(data[1:], columns=data[0])
                st.success(f"Trovate {len(df)} credenziali")
                
                tab1, tab2, tab3 = st.tabs(["Tabella", "CSV", "Download"])
                
                with tab1:
                    hide_pwd = st.checkbox("Nascondi password", value=True)
                    display_df = df.copy()
                    if hide_pwd and 'PASSWORD' in display_df.columns:
                        display_df['PASSWORD'] = '********'
                    st.dataframe(display_df, use_container_width=True)
                
                with tab2:
                    st.text_area("CSV:", decrypted_csv, height=300)
                
                with tab3:
                    st.download_button("Scarica CSV", decrypted_csv, "credenziali.csv", "text/csv")
        except Exception as e:
            st.error(f"Errore: {str(e)}")
