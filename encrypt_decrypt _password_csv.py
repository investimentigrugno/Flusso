import streamlit as st
import hashlib
import base64
import uuid
import pandas as pd
from io import StringIO
import os

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
