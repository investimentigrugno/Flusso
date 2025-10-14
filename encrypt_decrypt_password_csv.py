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

def parse_csv_row(row):
    return row.split(',')

def password_decryptor_app():
    st.title("CSV Password Decryptor")
    st.markdown("Decripta i tuoi file CSV")
    
    uploaded_file = st.file_uploader("Carica CSV:", type=['csv'])
    master_key = st.text_input("Chiave master:", type="password")
    
    if uploaded_file and master_key and len(master_key) >= 8:
        try:
            file_content = uploaded_file.read().decode('utf-8').strip()
            decrypted_csv = decrypt_data(file_content, master_key)
            st.success("Decriptazione riuscita!")
            st.text_area("Contenuto:", decrypted_csv, height=300)
        except Exception as e:
            st.error(f"Errore: {str(e)}")
