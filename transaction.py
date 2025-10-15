import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import requests
import json


@st.cache_data(ttl=120)
def load_sheet_csv_transactions(spreadsheet_id, gid):
    """Carica foglio pubblico via CSV export"""
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    
    # Retry con backoff
    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            df = pd.read_csv(url)
            if not df.empty:
                return df
            time.sleep(1)
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2)
    
    return None


def append_transaction_via_webhook(transaction_data, webhook_url):
    """
    Invia transazione al Google Apps Script webhook
    
    Args:
        transaction_data: Dizionario con i dati della transazione
        webhook_url: URL del webhook Google Apps Script
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Prepara i dati per il webhook
        payload = {
            "data": transaction_data['Data'],
            "operazione": transaction_data['Operazione'],
            "strumento": transaction_data['Strumento'],
            "pmc": transaction_data['PMC'],
            "quantita": transaction_data['Quantità'],
            "totale": transaction_data['Totale'],
            "valuta": transaction_data['Valuta'],
            "tasso_cambio": transaction_data['Tasso di cambio'],
            "commissioni": transaction_data['Commissioni'],
            "controvalore": transaction_data['Controvalore €']
        }
        
        # Invia richiesta POST al webhook
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        # Verifica la risposta
        if response.status_code == 200:
            result = response.json()
            return result.get('success', False), result.get('message', 'Risposta sconosciuta')
        else:
            return False, f"Errore HTTP {response.status_code}: {response.text}"
            
    except requests.exceptions.Timeout:
        return False, "Timeout: il server non ha risposto in tempo"
    except requests.exceptions.ConnectionError:
        return False, "Errore di connessione: verifica l'URL del webhook"
    except Exception as e:
        return False, f"Errore imprevisto: {str(e)}"


def transaction_tracker_app():
    """Applicazione Transaction Tracker"""
    
    st.title("💳 Transaction Tracker")
    st.markdown("---")
    
    # ID del foglio Google Sheets
    spreadsheet_id = "1mD9jxDJv26aZwCdIbvQVjlJGBhRwKWwQnPpPPq0ON5Y"
    gid_transactions = 1594640549
    
    # ==================== CONFIGURAZIONE WEBHOOK ====================
    # IMPORTANTE: Sostituisci questo URL con quello del tuo Google Apps Script
    WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbwBzXbal3FNV4uxTpXIM8FlRcFBaW1_dO_A08xS9CRHIfj44D7wpWJ3HR69ADsC7gO3oQ/exec"
    
    # Se non usi secrets, puoi inserire direttamente l'URL:
    # WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxxxxxxxxxxxxx/exec"
    
    # Opzioni sidebar
    st.sidebar.markdown("### ⚙️ Opzioni Transazioni")
    
    # Bottone refresh
    if st.sidebar.button("🔄 Aggiorna Transazioni", type="primary"):
        st.cache_data.clear()
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.caption("💡 I dati vengono aggiornati automaticamente ogni 2 minuti")
    
    # ==================== TABS ====================
    tab1, tab2, tab3 = st.tabs(["📊 Visualizza Transazioni", "➕ Aggiungi Transazione", "⚙️ Configurazione"])
    
    # ==================== TAB 1: VISUALIZZA TRANSAZIONI ====================
    with tab1:
        try:
            with st.spinner("Caricamento transazioni dal Google Sheet..."):
                df_transactions = load_sheet_csv_transactions(spreadsheet_id, gid_transactions)
            
            if df_transactions is None or df_transactions.empty:
                st.error("❌ Impossibile caricare il foglio 'Transaction'")
                st.info("💡 Verifica che il foglio sia pubblico: Condividi → Chiunque con il link → Visualizzatore")
                st.stop()
            
            # Definisci le intestazioni attese
            expected_columns = [
                'Data', 'Operazione', 'Strumento', 'PMC', 'Quantità', 
                'Totale', 'Valuta', 'Tasso di cambio', 'Commissioni', 'Controvalore €'
            ]
            
            # Se le colonne non corrispondono, usa le prime 10 colonne
            if len(df_transactions.columns) >= 10:
                df_transactions = df_transactions.iloc[:, :10]
                df_transactions.columns = expected_columns
            else:
                st.error(f"❌ Il foglio ha solo {len(df_transactions.columns)} colonne, ne servono almeno 10")
                st.stop()
            
            # Converti la colonna Data
            df_transactions['Data'] = pd.to_datetime(df_transactions['Data'], errors='coerce')
            
            # Rimuovi righe senza data valida
            df_transactions = df_transactions.dropna(subset=['Data'])
            
            # Ordina per data decrescente (più recenti prima)
            df_transactions = df_transactions.sort_values('Data', ascending=False)
            
            st.success(f"✅ {len(df_transactions)} transazioni caricate con successo!")
            
            # ==================== FILTRI SIDEBAR ====================
            st.sidebar.markdown("---")
            st.sidebar.markdown("### 🔍 Filtri")
            
            # Filtro per tipo di operazione
            operazioni_uniche = df_transactions['Operazione'].dropna().unique().tolist()
            operazione_filter = st.sidebar.multiselect(
                "Tipo Operazione",
                options=operazioni_uniche,
                default=operazioni_uniche
            )
            
            # Filtro per strumento
            strumenti_unici = sorted(df_transactions['Strumento'].dropna().unique().tolist())
            strumento_filter = st.sidebar.multiselect(
                "Strumento",
                options=strumenti_unici,
                default=[]
            )
            
            # Filtro per valuta
            valute_uniche = sorted(df_transactions['Valuta'].dropna().unique().tolist())
            valuta_filter = st.sidebar.multiselect(
                "Valuta",
                options=valute_uniche,
                default=[]
            )
            
            # Filtro per data
            min_date = df_transactions['Data'].min().date()
            max_date = df_transactions['Data'].max().date()
            
            date_range = st.sidebar.date_input(
                "Intervallo Date",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )
            
            # Applica filtri
            df_filtered_trans = df_transactions.copy()
            
            if operazione_filter:
                df_filtered_trans = df_filtered_trans[df_filtered_trans['Operazione'].isin(operazione_filter)]
            
            if strumento_filter:
                df_filtered_trans = df_filtered_trans[df_filtered_trans['Strumento'].isin(strumento_filter)]
            
            if valuta_filter:
                df_filtered_trans = df_filtered_trans[df_filtered_trans['Valuta'].isin(valuta_filter)]
            
            if len(date_range) == 2:
                start_date, end_date = date_range
                df_filtered_trans = df_filtered_trans[
                    (df_filtered_trans['Data'].dt.date >= start_date) & 
                    (df_filtered_trans['Data'].dt.date <= end_date)
                ]
            
            # ==================== TABELLA TRANSAZIONI ====================
            st.markdown("---")
            st.subheader("📋 DETTAGLIO TRANSAZIONI")
            
            # Formatta la data per visualizzazione
            df_display = df_filtered_trans.copy()
            df_display['Data'] = df_display['Data'].dt.strftime('%d/%m/%Y')
            
            # Mostra tabella
            st.dataframe(
                df_display[expected_columns],
                use_container_width=True,
                height=500,
                hide_index=True
            )
            
            # ==================== EXPORT CSV ====================
            st.markdown("---")
            
            csv = df_display.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Scarica Transazioni Filtrate (CSV)",
                data=csv,
                file_name=f"transazioni_portfolio_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        except Exception as e:
            st.error(f"❌ Errore nel caricamento delle transazioni: {str(e)}")
            st.info("💡 Verifica che il foglio Google Sheets sia pubblicamente accessibile.")
            
            with st.expander("🔍 Dettagli errore"):
                st.code(str(e))
    
    # ==================== TAB 2: AGGIUNGI TRANSAZIONE ====================
    with tab2:
        st.subheader("➕ Aggiungi Nuova Transazione")
        st.markdown("---")
        
        # Verifica configurazione webhook
        if WEBHOOK_URL == "https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec":
            st.error("⚠️ URL del webhook non configurato!")
            st.info("Vai al tab 'Configurazione' per impostare l'URL del webhook Google Apps Script.")
            st.stop()
        
        # Carica dati per suggerimenti
        try:
            df_existing = load_sheet_csv_transactions(spreadsheet_id, gid_transactions)
            if df_existing is not None and not df_existing.empty:
                existing_operazioni = df_existing.iloc[:, 1].dropna().unique().tolist() if len(df_existing.columns) > 1 else []
                existing_strumenti = df_existing.iloc[:, 2].dropna().unique().tolist() if len(df_existing.columns) > 2 else []
                existing_valute = df_existing.iloc[:, 6].dropna().unique().tolist() if len(df_existing.columns) > 6 else []
            else:
                existing_operazioni = []
                existing_strumenti = []
                existing_valute = []
        except:
            existing_operazioni = []
            existing_strumenti = []
            existing_valute = []
        
        # Valori di default comuni
        default_operazioni = ["Acquisto", "Vendita", "Dividendo", "Interesse", "Prelievo", "Deposito"]
        default_valute = ["EUR", "USD", "GBP", "CHF"]
        
        # Combina valori esistenti con defaults
        operazioni_options = list(set(existing_operazioni + default_operazioni))
        valute_options = list(set(existing_valute + default_valute))
        
        with st.form("new_transaction_form", clear_on_submit=True):
            st.markdown("### 📝 Dettagli Transazione")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # 1. Data
                data_input = st.date_input(
                    "Data *",
                    value=datetime.now(),
                    help="Data della transazione"
                )
                
                # 2. Operazione
                operazione_input = st.selectbox(
                    "Operazione *",
                    options=operazioni_options,
                    help="Tipo di operazione"
                )
                
                # 3. Strumento
                strumento_input = st.text_input(
                    "Strumento *",
                    placeholder="Es: AAPL, BTC-USD, TSLA",
                    help="Nome dello strumento finanziario"
                )
                
                # 4. PMC (Prezzo Medio di Carico)
                pmc_input = st.number_input(
                    "PMC (Prezzo Medio) *",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.4f",
                    help="Prezzo medio di carico/vendita"
                )
                
                # 5. Quantità
                quantita_input = st.number_input(
                    "Quantità *",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.4f",
                    help="Quantità acquistata/venduta"
                )
            
            with col2:
                # 7. Valuta
                valuta_input = st.selectbox(
                    "Valuta *",
                    options=valute_options,
                    help="Valuta della transazione"
                )
                
                # 8. Tasso di cambio
                tasso_cambio_input = st.number_input(
                    "Tasso di Cambio *",
                    min_value=0.0,
                    value=1.0,
                    step=0.0001,
                    format="%.4f",
                    help="Tasso di cambio verso EUR (1.0 se già in EUR)"
                )
                
                # 9. Commissioni
                commissioni_input = st.number_input(
                    "Commissioni",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.2f",
                    help="Commissioni applicate alla transazione"
                )
            
            st.markdown("---")
            st.markdown("### 📊 Riepilogo Calcoli Automatici")
            
            # Calcoli automatici
            totale_calcolato = pmc_input * quantita_input
            controvalore_calcolato = totale_calcolato * tasso_cambio_input
            
            col_calc1, col_calc2 = st.columns(2)
            
            with col_calc1:
                st.metric(
                    label=f"Totale (calcolato in {valuta_input})",
                    value=f"{totale_calcolato:,.2f}",
                    help="PMC × Quantità"
                )
            
            with col_calc2:
                st.metric(
                    label="Controvalore € (calcolato)",
                    value=f"€{controvalore_calcolato:,.2f}",
                    help="Totale × Tasso di Cambio"
                )
            
            st.markdown("---")
            
            # Bottoni form
            col_btn1, col_btn2 = st.columns([3, 1])
            
            with col_btn1:
                submitted = st.form_submit_button(
                    "💾 Salva Transazione",
                    type="primary",
                    use_container_width=True
                )
            
            with col_btn2:
                reset = st.form_submit_button(
                    "🔄 Reset",
                    use_container_width=True
                )
        
        # Gestione submit
        if submitted:
            # Validazione
            errors = []
            
            if not strumento_input:
                errors.append("⚠️ Il campo 'Strumento' è obbligatorio")
            
            if pmc_input <= 0:
                errors.append("⚠️ Il 'PMC' deve essere maggiore di 0")
            
            if quantita_input <= 0:
                errors.append("⚠️ La 'Quantità' deve essere maggiore di 0")
            
            if tasso_cambio_input <= 0:
                errors.append("⚠️ Il 'Tasso di Cambio' deve essere maggiore di 0")
            
            if errors:
                for error in errors:
                    st.error(error)
            else:
                # Crea nuova transazione
                new_transaction = {
                    'Data': data_input.strftime('%d/%m/%Y'),
                    'Operazione': operazione_input,
                    'Strumento': strumento_input,
                    'PMC': f"{pmc_input:.4f}",
                    'Quantità': f"{quantita_input:.4f}",
                    'Totale': f"{totale_calcolato:.2f}",
                    'Valuta': valuta_input,
                    'Tasso di cambio': f"{tasso_cambio_input:.4f}",
                    'Commissioni': f"{commissioni_input:.2f}",
                    'Controvalore €': f"{controvalore_calcolato:.2f}"
                }
                
                # Invia al webhook
                with st.spinner("💾 Salvataggio transazione in corso..."):
                    success, message = append_transaction_via_webhook(new_transaction, WEBHOOK_URL)
                
                if success:
                    st.success(f"✅ {message}")
                    st.balloons()
                    
                    # Mostra anteprima
                    st.markdown("### 👀 Transazione Salvata")
                    df_preview = pd.DataFrame([new_transaction])
                    st.dataframe(df_preview, use_container_width=True, hide_index=True)
                    
                    # Pulisci cache
                    st.cache_data.clear()
                    
                    st.info("🔄 Torna al tab 'Visualizza Transazioni' e clicca 'Aggiorna' per vedere la nuova transazione.")
                else:
                    st.error(f"❌ {message}")
                    st.warning("Verifica che l'URL del webhook sia corretto nel tab 'Configurazione'.")
                    
                    # Offri download CSV come fallback
                    df_preview = pd.DataFrame([new_transaction])
                    csv_new = df_preview.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Scarica Transazione (CSV Backup)",
                        data=csv_new,
                        file_name=f"transazione_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
        
        # Suggerimenti
        with st.expander("💡 Suggerimenti per compilare il form"):
            st.markdown("""
            - **Data**: Seleziona la data effettiva della transazione
            - **Operazione**: Scegli tra Acquisto, Vendita, Dividendo, etc.
            - **Strumento**: Inserisci il ticker o nome dell'asset (es: AAPL, BTC-USD)
            - **PMC**: Prezzo unitario al quale hai comprato/venduto
            - **Quantità**: Numero di unità/azioni/quote
            - **Valuta**: Valuta originale della transazione
            - **Tasso di Cambio**: Se la valuta è EUR, lascia 1.0. Altrimenti inserisci il cambio EUR/VALUTA
            - **Commissioni**: Costi di intermediazione applicati dal broker
            
            I campi **Totale** e **Controvalore €** vengono calcolati automaticamente.
            """)
    
    # ==================== TAB 3: CONFIGURAZIONE ====================
    with tab3:
        st.subheader("⚙️ Configurazione Webhook")
        st.markdown("---")
        
        st.markdown("""
        ### Come configurare il webhook Google Apps Script
        
        **Passo 1: Crea lo script**
        1. Apri il tuo Google Sheet
        2. Vai su **Extensions** → **Apps Script**
        3. Incolla il codice fornito nella documentazione
        4. Salva il progetto
        
        **Passo 2: Deploy come Web App**
        1. Clicca **Deploy** → **New deployment**
        2. Seleziona tipo **Web app**
        3. Imposta "Who has access" su **Anyone**
        4. Clicca **Deploy**
        5. Copia l'URL generato
        
        **Passo 3: Configura l'URL**
        """)
        
        st.info(f"**URL attuale configurato:**\n``````")
        
        if WEBHOOK_URL == "https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec":
            st.warning("⚠️ URL del webhook non ancora configurato!")
        
        st.markdown("""
        ### Metodi di configurazione:
        
        **Opzione 1: Streamlit Secrets (consigliato per deploy)**
        
        Crea il file `.streamlit/secrets.toml`:
        ```
        webhook_url = "https://script.google.com/macros/s/TUO_SCRIPT_ID/exec"
        ```
        
        **Opzione 2: Hardcode nel codice**
        
        Modifica la riga nel codice:
        ```
        WEBHOOK_URL = "https://script.google.com/macros/s/TUO_SCRIPT_ID/exec"
        ```
        """)
        
        # Test webhook
        st.markdown("---")
        st.markdown("### 🧪 Test Webhook")
        
        if st.button("🧪 Testa Connessione Webhook", use_container_width=True):
            with st.spinner("Test connessione in corso..."):
                try:
                    response = requests.get(WEBHOOK_URL, timeout=10)
                    if response.status_code == 200:
                        st.success("✅ Webhook raggiungibile e funzionante!")
                        st.json(response.json())
                    else:
                        st.error(f"❌ Errore HTTP {response.status_code}")
                except Exception as e:
                    st.error(f"❌ Errore di connessione: {str(e)}")
