import streamlit as st
import hashlib
import base64
import uuid
import pandas as pd
from io import StringIO
import os


# ============================================================================
# FUNZIONI DI CRITTOGRAFIA
# ============================================================================


def encrypt_data(plaintext, key):
    """Cripta i dati usando la chiave master"""
    try:
        # Genera un salt casuale
        salt = str(uuid.uuid4())
        
        # Genera chiave derivata
        derived_key = hashlib.sha256((key + salt).encode('utf-8')).digest()
        key_base64 = base64.b64encode(derived_key).decode('utf-8')
        
        # Cripta con XOR
        encrypted = xor_encrypt(plaintext, key_base64)
        
        # Combina salt e dati crittografati
        combined = f"{salt}::{encrypted}"
        
        # Codifica in Base64
        return base64.b64encode(combined.encode('utf-8')).decode('utf-8')
    except Exception as e:
        raise Exception(f'Crittografia fallita: {str(e)}')


def xor_encrypt(plaintext, key):
    """Crittografia XOR"""
    result = []
    for i, char in enumerate(plaintext):
        key_char = ord(key[i % len(key)])
        plain_char = ord(char)
        result.append(chr(plain_char ^ key_char))
    
    encrypted = ''.join(result)
    return base64.b64encode(encrypted.encode('utf-8')).decode('utf-8')


# ============================================================================
# FUNZIONI DI DECRITTOGRAFIA
# ============================================================================


def decrypt_data(encrypted_data, key):
    """Decripta i dati usando la chiave master"""
    try:
        # Decodifica Base64
        decoded = base64.b64decode(encrypted_data).decode('utf-8')
        
        # Separa salt e dati
        parts = decoded.split('::')
        if len(parts) != 2:
            raise Exception('Formato dati non valido')
        
        salt = parts[0]
        encrypted = parts[1]
        
        # Rigenera la chiave derivata
        derived_key = hashlib.sha256((key + salt).encode('utf-8')).digest()
        key_base64 = base64.b64encode(derived_key).decode('utf-8')
        
        # Decripta
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
                # Doppia virgoletta = virgoletta escaped
                cell += '"'
                i += 1
            else:
                # Toggle modalità quote
                in_quotes = not in_quotes
        elif char == ',' and not in_quotes:
            # Fine cella
            cells.append(cell)
            cell = ''
        else:
            cell += char
        
        i += 1
    
    # Aggiungi ultima cella
    cells.append(cell)
    return cells


# ============================================================================
# FUNZIONE PRINCIPALE PER IL MAIN
# ============================================================================


def password_decryptor_app():
    """App principale per decrittografare CSV"""
    
    # Inizializza session state per gestire modifiche
    if 'edited_df' not in st.session_state:
        st.session_state.edited_df = None
    if 'master_key_stored' not in st.session_state:
        st.session_state.master_key_stored = None
    if 'edit_mode' not in st.session_state:
        st.session_state.edit_mode = False
    
    # Header principale
    st.title("🔐 CSV Password Decryptor")
    st.markdown("**Decripta in sicurezza i tuoi file CSV di credenziali crittografati**")
    
    # Sidebar con informazioni
    with st.sidebar:
        st.header("ℹ️ Informazioni")
        st.markdown("""
        ### Come usare:
        1. **Carica** il file CSV crittografato
        2. **Inserisci** la chiave master
        3. **Visualizza** la tabella con i dati
        4. **Scarica** il CSV in chiaro (opzionale)
        
        ### ✨ NUOVO - Modifica credenziali:
        5. **Attiva modalità modifica**
        6. **Aggiungi/Modifica/Elimina** righe
        7. **Ri-cripta** e scarica il file aggiornato
        
        ### Sicurezza:
        ✅ **Decriptazione locale**
        - I dati non vengono inviati a server esterni
        
        ✅ **Nessun salvataggio**
        - I file vengono elaborati solo in memoria
        
        ✅ **Compatibile**
        - Google Apps Script Password Manager
        
        ### Formato supportato:
        - File .csv crittografati
        - Struttura: SITO | EMAIL/IBAN | PASSWORD | PIN | NOTE
        - Chiave master (min 8 caratteri)
        """)
    
    # Sezione principale
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📁 Carica File Crittografato")
        
        # File uploader
        uploaded_file = st.file_uploader(
            "Seleziona il file CSV crittografato:",
            type=['csv'],
            help="Carica il file .csv generato dal Google Apps Script Password Manager"
        )
        
        if uploaded_file is not None:
            # Leggi il contenuto del file
            file_content = uploaded_file.read().decode('utf-8').strip()
            st.success(f"✅ File caricato: **{uploaded_file.name}**")
            st.info(f"📊 Dimensione: {len(file_content)} caratteri")
            
            # Mostra anteprima del contenuto crittografato (primi 100 caratteri)
            with st.expander("👁️ Anteprima contenuto crittografato"):
                st.code(file_content[:100] + "..." if len(file_content) > 100 else file_content)
    
    with col2:
        st.header("🔑 Chiave Master")
        
        # Input per la chiave master
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
                st.session_state.master_key_stored = master_key
                st.success(f"✅ Chiave inserita ({len(master_key)} caratteri)")
    
    # Sezione decriptazione - TABELLA SUBITO VISIBILE (FUNZIONALITÀ ORIGINALE)
    if uploaded_file is not None and master_key and len(master_key) >= 8:
        
        try:
            with st.spinner("🔄 Decriptazione in corso..."):
                # Decripta il contenuto
                decrypted_csv = decrypt_data(file_content, master_key)
                
                # Converti CSV in array usando pandas per essere sicuri
                try:
                    # Prova prima con pandas
                    from io import StringIO
                    df = pd.read_csv(StringIO(decrypted_csv))
                except:
                    # Se fallisce, usa il parser manuale
                    rows = decrypted_csv.split('\n')
                    data = [parse_csv_row(row) for row in rows if row.strip()]
                    if len(data) > 1:
                        df = pd.DataFrame(data[1:], columns=data[0])
                    else:
                        df = pd.DataFrame()
                
                # Salva in session state per le modifiche
                if st.session_state.edited_df is None:
                    st.session_state.edited_df = df.copy()
            
            if not df.empty:
                st.success(f"✅ **Decriptazione riuscita!** Caricate {len(df)} credenziali")
                
                # MOSTRA SUBITO LA TABELLA INTERATTIVA - NIENTE TABS (FUNZIONALITÀ ORIGINALE)
                st.markdown("---")
                st.header("📊 Credenziali Decriptate")
                
                # Opzione per nascondere le password (FUNZIONALITÀ ORIGINALE)
                col_check1, col_check2, col_space = st.columns([1, 1, 2])
                with col_check1:
                    hide_passwords = st.checkbox("🙈 Nascondi password", value=True)
                
                # NUOVA FUNZIONALITÀ: Toggle modalità modifica
                with col_check2:
                    edit_mode = st.checkbox("✏️ Modalità modifica", value=st.session_state.edit_mode)
                    st.session_state.edit_mode = edit_mode
                
                # Prepara il dataframe per la visualizzazione
                if edit_mode:
                    # MODALITÀ MODIFICA: Editor interattivo
                    st.info("✏️ **Modalità modifica attiva** - Puoi aggiungere, modificare o eliminare righe")
                    
                    edited_df = st.data_editor(
                        st.session_state.edited_df,
                        num_rows="dynamic",  # Permette aggiunta/eliminazione righe
                        use_container_width=True,
                        hide_index=False,
                        height=min(600, max(200, len(st.session_state.edited_df) * 35 + 150)),
                        key="credential_editor"
                    )
                    
                    # Aggiorna il session state
                    st.session_state.edited_df = edited_df
                    
                else:
                    # MODALITÀ VISUALIZZAZIONE: Tabella sola lettura (FUNZIONALITÀ ORIGINALE)
                    display_df = df.copy()
                    if hide_passwords:
                        password_cols = [col for col in df.columns if 'PASSWORD' in col.upper() or 'PWD' in col.upper()]
                        for col in password_cols:
                            display_df[col] = display_df[col].apply(
                                lambda x: '••••••••' if pd.notna(x) and str(x).strip() else ''
                            )
                    
                    # TABELLA INTERATTIVA PRINCIPALE (FUNZIONALITÀ ORIGINALE)
                    st.dataframe(
                        display_df,
                        use_container_width=True,
                        hide_index=True,
                        height=min(600, max(200, len(df) * 35 + 100))  # Altezza dinamica
                    )
                
                # Statistiche sotto la tabella (FUNZIONALITÀ ORIGINALE)
                col_stat1, col_stat2, col_stat3 = st.columns(3)
                with col_stat1:
                    st.metric("📈 Credenziali", len(st.session_state.edited_df if edit_mode else df))
                with col_stat2:
                    st.metric("📋 Colonne", len(df.columns))
                with col_stat3:
                    # Conta quante hanno password non vuote
                    password_cols = [col for col in df.columns if 'PASSWORD' in col.upper()]
                    if password_cols:
                        has_pwd = df[password_cols[0]].notna().sum()
                        st.metric("🔑 Con password", has_pwd)
                    else:
                        st.metric("🔑 Con password", "N/A")
                
                # Sezione download (FUNZIONALITÀ ORIGINALE + NUOVA)
                st.markdown("---")
                st.header("💾 Download")
                
                # Genera timestamp per il nome del file
                timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
                
                if edit_mode:
                    # NUOVA FUNZIONALITÀ: Download file modificato e crittografato
                    col_down1, col_down2 = st.columns([1, 1])
                    
                    with col_down1:
                        st.subheader("📥 CSV in Chiaro")
                        csv_plaintext = st.session_state.edited_df.to_csv(index=False)
                        st.download_button(
                            label="📥 Scarica CSV Decriptato",
                            data=csv_plaintext,
                            file_name=f"credenziali_decriptate_{timestamp}.csv",
                            mime='text/csv',
                            help="Scarica il file CSV modificato in chiaro",
                            use_container_width=True
                        )
                        st.warning("⚠️ File in chiaro")
                    
                    with col_down2:
                        st.subheader("🔒 CSV Crittografato")
                        
                        if st.button("🔐 Ri-Cripta File", type="primary", use_container_width=True):
                            try:
                                with st.spinner("🔄 Crittografia in corso..."):
                                    # Converti dataframe modificato in CSV
                                    csv_to_encrypt = st.session_state.edited_df.to_csv(index=False)
                                    
                                    # Cripta con la stessa chiave master
                                    encrypted_csv = encrypt_data(csv_to_encrypt, st.session_state.master_key_stored)
                                    
                                    st.success("✅ File crittografato!")
                                    
                                    st.download_button(
                                        label="💾 Scarica File Crittografato",
                                        data=encrypted_csv,
                                        file_name=f"credenziali_crittografate_{timestamp}.csv",
                                        mime='text/csv',
                                        help="Scarica il file CSV crittografato aggiornato",
                                        use_container_width=True,
                                        type="primary"
                                    )
                            except Exception as e:
                                st.error(f"❌ Errore crittografia: {str(e)}")
                
                else:
                    # FUNZIONALITÀ ORIGINALE: Download solo CSV in chiaro
                    download_filename = f"credenziali_decriptate_{timestamp}.csv"
                    
                    col_down1, col_down2 = st.columns([1, 2])
                    with col_down1:
                        st.download_button(
                            label="📥 Scarica CSV Decriptato",
                            data=decrypted_csv,
                            file_name=download_filename,
                            mime='text/csv',
                            help="Scarica il file CSV con i dati in chiaro",
                            use_container_width=True
                        )
                    
                    with col_down2:
                        st.warning("""
                        ⚠️ **ATTENZIONE SICUREZZA:**  
                        Il file conterrà le credenziali in chiaro. Conservalo in luogo sicuro!
                        """)
                
            else:
                st.error("❌ Nessun dato trovato nel file decriptato")
                
        except Exception as e:
            st.error(f"❌ **Errore durante la decriptazione:**")
            st.code(str(e))
            st.info("""
            **Possibili cause:**
            - ❌ Chiave master errata
            - ❌ File corrotto o non valido
            - ❌ Formato file non supportato
            
            **Soluzioni:**
            - ✅ Verifica la chiave master
            - ✅ Controlla che il file non sia stato modificato
            - ✅ Assicurati che il file sia stato generato correttamente
            """)
    
    # Footer (FUNZIONALITÀ ORIGINALE)
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center'>
        <p><strong>CSV Password Decryptor</strong> | Sicuro • Privato • Open Source</p>
        <p>Compatibile con Google Apps Script Password Manager</p>
    </div>
    """, unsafe_allow_html=True)


# ============================================================================
# ESECUZIONE APP
# ============================================================================

if __name__ == "__main__":
    password_decryptor_app()
