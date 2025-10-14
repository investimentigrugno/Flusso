import streamlit as st
import hashlib
import base64
import uuid
import pandas as pd
from io import StringIO
import os

# ============================================================================
# FUNZIONI DI CRITTOGRAFIA E DECRITTOGRAFIA
# ============================================================================

def encrypt_data(data, key):
    """Cripta i dati usando la chiave master"""
    try:
        # Genera un salt casuale
        salt = str(uuid.uuid4())
        
        # Genera chiave derivata
        derived_key = hashlib.sha256((key + salt).encode('utf-8')).digest()
        key_base64 = base64.b64encode(derived_key).decode('utf-8')
        
        # Cripta i dati
        encrypted = xor_encrypt(data, key_base64)
        
        # Combina salt e dati crittografati
        combined = f"{salt}::{encrypted}"
        
        # Codifica in Base64
        return base64.b64encode(combined.encode('utf-8')).decode('utf-8')
    except Exception as e:
        raise Exception(f'Crittografia fallita: {str(e)}')

def xor_encrypt(data, key):
    """Crittografia XOR"""
    result = []
    for i, char in enumerate(data):
        key_char = ord(key[i % len(key)])
        data_char = ord(char)
        result.append(chr(data_char ^ key_char))
    
    encrypted = ''.join(result)
    return base64.b64encode(encrypted.encode('utf-8')).decode('utf-8')

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
# APP ENCRYPT
# ============================================================================

def password_encryptor_app():
    """App per crittografare CSV"""
    
    # Header principale
    st.title("🔒 CSV Password Encryptor")
    st.markdown("**Cripta in sicurezza i tuoi file CSV di credenziali**")
    
    # Sidebar con informazioni
    with st.sidebar:
        st.header("ℹ️ Informazioni")
        st.markdown("""
        ### Come usare:
        1. **Carica** il file CSV in chiaro
        2. **Inserisci** la chiave master
        3. **Scarica** il CSV crittografato
        
        ### Sicurezza:
        ✅ **Crittografia locale**
        - I dati non vengono inviati a server esterni
        
        ✅ **Nessun salvataggio**
        - I file vengono elaborati solo in memoria
        
        ✅ **Compatibile**
        - Google Apps Script Password Manager
        
        ### Formato supportato:
        - File .csv in chiaro
        - Struttura: SITO | EMAIL/IBAN | PASSWORD | PIN | NOTE
        - Chiave master (min 8 caratteri)
        """)
    
    # Sezione principale
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📁 Carica File da Crittografare")
        
        # File uploader
        uploaded_file = st.file_uploader(
            "Seleziona il file CSV in chiaro:",
            type=['csv'],
            key="encrypt_uploader",
            help="Carica il file .csv che vuoi crittografare"
        )
        
        if uploaded_file is not None:
            # Leggi il contenuto del file
            file_content = uploaded_file.read().decode('utf-8')
            st.success(f"✅ File caricato: **{uploaded_file.name}**")
            st.info(f"📊 Dimensione: {len(file_content)} caratteri")
            
            # Mostra anteprima del contenuto (primi 200 caratteri)
            with st.expander("👁️ Anteprima contenuto"):
                st.code(file_content[:200] + "..." if len(file_content) > 200 else file_content)
    
    with col2:
        st.header("🔑 Chiave Master")
        
        # Input per la chiave master
        master_key = st.text_input(
            "Inserisci la chiave master per crittografia:",
            type="password",
            key="encrypt_key",
            help="Usa una chiave forte (min 8 caratteri). Ricordala bene!",
            placeholder="Minimum 8 caratteri..."
        )
        
        # Conferma chiave
        confirm_key = st.text_input(
            "Conferma la chiave master:",
            type="password",
            key="confirm_encrypt_key",
            help="Reinserisci la stessa chiave",
            placeholder="Conferma chiave..."
        )
        
        if master_key:
            if len(master_key) < 8:
                st.error("❌ La chiave deve essere almeno 8 caratteri!")
            else:
                st.success(f"✅ Chiave inserita ({len(master_key)} caratteri)")
        
        if master_key and confirm_key:
            if master_key != confirm_key:
                st.error("❌ Le chiavi non corrispondono!")
            else:
                st.success("✅ Chiavi corrispondenti!")
    
    # Sezione crittografia
    if uploaded_file is not None and master_key and confirm_key and master_key == confirm_key and len(master_key) >= 8:
        st.header("🔐 Crittografia")
        
        try:
            with st.spinner("🔄 Crittografia in corso..."):
                # Cripta il contenuto
                encrypted_content = encrypt_data(file_content, master_key)
            
            st.success("✅ **Crittografia completata con successo!**")
            
            # Tabs per diverse opzioni
            tab1, tab2 = st.tabs(["💾 Download", "👁️ Anteprima"])
            
            with tab1:
                st.subheader("Scarica File Crittografato")
                
                # Genera timestamp per il nome del file
                timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
                download_filename = f"encrypted_{timestamp}.csv"
                
                st.download_button(
                    label="📥 Scarica CSV Crittografato",
                    data=encrypted_content,
                    file_name=download_filename,
                    mime='text/csv',
                    help="Scarica il file CSV crittografato"
                )
                
                st.info(f"""
                📋 **Informazioni file:**
                - Nome: `{download_filename}`
                - Dimensione: {len(encrypted_content)} caratteri
                - Algoritmo: XOR + Base64
                - Salt: Generato automaticamente
                """)
                
                st.warning("""
                ⚠️ **IMPORTANTE:**
                - **Conserva la chiave master in un luogo sicuro**
                - Senza la chiave non potrai decrittare i dati
                - Non condividere la chiave tramite canali non sicuri
                """)
            
            with tab2:
                st.subheader("Anteprima Contenuto Crittografato")
                
                preview_length = st.slider(
                    "Lunghezza anteprima:",
                    min_value=50,
                    max_value=500,
                    value=200,
                    step=50
                )
                
                preview = encrypted_content[:preview_length]
                if len(encrypted_content) > preview_length:
                    preview += "..."
                
                st.code(preview)
                st.caption(f"Mostrando {min(preview_length, len(encrypted_content))} di {len(encrypted_content)} caratteri totali")
                
        except Exception as e:
            st.error(f"❌ **Errore durante la crittografia:**\n{str(e)}")
            st.info("""
            **Possibili cause:**
            - File non valido
            - Formato CSV non supportato
            - Errore di codifica
            
            **Soluzioni:**
            - Verifica che il file sia un CSV valido
            - Assicurati che il file sia codificato in UTF-8
            """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center'>
        <p><strong>CSV Password Encryptor</strong> | Sicuro • Privato • Open Source</p>
        <p>Compatibile con Google Apps Script Password Manager</p>
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# APP DECRYPT
# ============================================================================

def password_decryptor_app():
    """App per decrittografare CSV"""
    
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
        3. **Visualizza** i dati decriptati
        4. **Scarica** il CSV in chiaro (opzionale)
        
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
                st.success(f"✅ Chiave inserita ({len(master_key)} caratteri)")
    
    # Sezione decriptazione
    if uploaded_file is not None and master_key and len(master_key) >= 8:
        st.header("🔓 Decriptazione")
        
        try:
            with st.spinner("🔄 Decriptazione in corso..."):
                # Decripta il contenuto
                decrypted_csv = decrypt_data(file_content, master_key)
                
                # Converti CSV in array
                rows = decrypted_csv.split('\n')
                data = [parse_csv_row(row) for row in rows if row.strip()]
            
            if 
                st.success(f"✅ **Decriptazione riuscita!** Caricate {len(data)-1} credenziali")
                
                # Crea DataFrame per la visualizzazione
                if len(data) > 1:  # Almeno intestazione + 1 riga di dati
                    df = pd.DataFrame(data[1:], columns=data[0])
                    
                    # Tabs per diverse visualizzazioni
                    tab1, tab2, tab3 = st.tabs(["📊 Tabella", "📋 Dati Grezzi", "💾 Download"])
                    
                    with tab1:
                        st.subheader("Credenziali Decriptate")
                        
                        # Opzione per nascondere le password
                        hide_passwords = st.checkbox("🙈 Nascondi password", value=True)
                        
                        display_df = df.copy()
                        if hide_passwords and 'PASSWORD' in display_df.columns:
                            display_df['PASSWORD'] = display_df['PASSWORD'].apply(
                                lambda x: '*' * min(len(str(x)), 12) if pd.notna(x) and str(x).strip() else ''
                            )
                        
                        st.dataframe(
                            display_df,
                            use_container_width=True,
                            height=400
                        )
                        
                        st.info(f"📈 **Statistiche:** {len(df)} credenziali | {len(df.columns)} colonne")
                    
                    with tab2:
                        st.subheader("Dati CSV Grezzi")
                        
                        st.text_area(
                            "Contenuto CSV completo:",
                            decrypted_csv,
                            height=300,
                            help="Dati CSV in formato testuale"
                        )
                    
                    with tab3:
                        st.subheader("Scarica File Decriptato")
                        
                        # Genera timestamp per il nome del file
                        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
                        download_filename = f"credenziali_decriptate_{timestamp}.csv"
                        
                        st.download_button(
                            label="📥 Scarica CSV Decriptato",
                            data=decrypted_csv,
                            file_name=download_filename,
                            mime='text/csv',
                            help="Scarica il file CSV con i dati in chiaro"
                        )
                        
                        st.warning("""
                        ⚠️ **ATTENZIONE SICUREZZA:**
                        - Il file scaricato conterrà le credenziali in chiaro
                        - Conservalo in luogo sicuro
                        - Considera di eliminarlo dopo l'uso
                        - Non condividerlo tramite canali non sicuri
                        """)
                else:
                    st.warning("⚠️ Il file sembra essere vuoto o contiene solo l'intestazione")
            else:
                st.error("❌ Nessun dato trovato nel file decriptato")
                
        except Exception as e:
            st.error(f"❌ **Errore durante la decriptazione:**\n{str(e)}")
            st.info("""
            **Possibili cause:**
            - Chiave master errata
            - File corrotto o non valido
            - Formato file non supportato
            
            **Soluzioni:**
            - Verifica la chiave master
            - Assicurati che il file sia stato generato correttamente
            - Controlla che il file non sia stato modificato
            """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center'>
        <p><strong>CSV Password Decryptor</strong> | Sicuro • Privato • Open Source</p>
        <p>Compatibile con Google Apps Script Password Manager</p>
    </div>
    """, unsafe_allow_html=True)
