# transaction_FIXED.py - VERSIONE CORRETTA CON TUTTI I BUG RISOLTI
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import requests
import json
import time

# ==================== FUNZIONI ====================

@st.cache_data(ttl=120)
def load_sheet_csv_transactions(spreadsheet_id, gid):
    """Carica foglio pubblico via CSV export"""
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    
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

def format_decimal(value):
    """Converte numero in stringa con virgola come separatore decimale"""
    if isinstance(value, str):
        return value.replace('.', ',')
    elif isinstance(value, (int, float)):
        return str(value).replace('.', ',')
    return str(value)

def append_transaction_via_webhook(transaction_data, webhook_url):
    """
    Invia transazione al Google Apps Script webhook
    """
    try:
        # Prepara i dati per il webhook con virgole come separatore
        payload = {
            "data": transaction_data['Data'],
            "operazione": transaction_data['Operazione'],
            "strumento": transaction_data['Strumento'],
            "pmc": format_decimal(transaction_data.get('PMC', 0)),
            "quantita": format_decimal(transaction_data.get('Quantita', 0)),
            "totale": format_decimal(transaction_data.get('Totale', 0)),
            "valuta": transaction_data['Valuta'],
            "tasso_cambio": format_decimal(transaction_data.get('Tasso_cambio', 1)),
            "commissioni": format_decimal(transaction_data.get('Commissioni', 0)),
            "controvalore": format_decimal(transaction_data.get('Controvalore', 0)),
            "lungo_breve": transaction_data.get('Lungo_breve', ''),
            "nome_strumento": transaction_data.get('Nome_strumento', transaction_data.get('Strumento', ''))
        }
        
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )

        # Verifica la risposta
        if response.status_code == 200:

            try:
                result = response.json()
                return result.get('success', False), result.get('message', 'Risposta sconosciuta')
            except json.JSONDecodeError as je:
                return False, f"❌ JSON non valido. Risposta: {response.text[:200]}"
        else:
            return False, f"Errore HTTP {response.status_code}: {response.text[:200]}"
    
    except requests.exceptions.Timeout:
        return False, "⏱️ Timeout: il server non ha risposto in tempo (> 10 secondi)"
    
    except requests.exceptions.ConnectionError:
        return False, "❌ Errore di connessione: verifica che il webhook sia raggiungibile"
    
    except Exception as e:
        return False, f"❌ Errore imprevisto: {str(e)}"


# ==================== APP PRINCIPALE ====================

def transaction_tracker_app():
    """Applicazione Transaction Tracker"""
    st.set_page_config(
        page_title="💳 Transaction Tracker",
        page_icon="💳",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("💳 Transaction Tracker")
    st.markdown("---")
    
    # Configurazione
    spreadsheet_id = "1mD9jxDJv26aZwCdIbvQVjlJGBhRwKWwQnPpPPq0ON5Y"
    gid_transactions = 1594640549
    
    # ⚠️ IMPORTANTE: Sostituisci questo URL con il TUO webhook Google Apps Script
    WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyu8f1-wz-UA7NAsiYmX0hRUgUiRv3pEmCYwYWMi9uQZAAoddPfHxN3iz1ldfY3fc0u/exec"
    
    # Sidebar
    st.sidebar.markdown("### ⚙️ Opzioni Transazioni")
    
    if st.sidebar.button("🔄 Aggiorna Transazioni", type="primary"):
        st.cache_data.clear()
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.caption("💡 I dati vengono aggiornati automaticamente ogni 2 minuti")
    
    # ==================== TABS ====================
    tab1, tab2, tab3 = st.tabs([
        "📊 Visualizza Transazioni",
        "➕ Aggiungi Transazione",
        "⚙️ Configurazione"
    ])
    
    # ==================== TAB 1: VISUALIZZA ====================
    with tab1:
        try:
            with st.spinner("📥 Caricamento transazioni dal Google Sheet..."):
                df_transactions = load_sheet_csv_transactions(spreadsheet_id, gid_transactions)
            
            if df_transactions is None or df_transactions.empty:
                st.error("❌ Impossibile caricare il foglio 'Transaction'")
                st.info("💡 Verifica che il foglio sia pubblico")
                st.stop()
            
            expected_columns = [
                'Data', 'Operazione', 'Strumento', 'PMC', 'Quantità',
                'Totale', 'Valuta', 'Tasso di cambio', 'Commissioni', 'Controvalore €'
            ]
            
            if len(df_transactions.columns) >= 10:
                df_transactions = df_transactions.iloc[:, :10]
                df_transactions.columns = expected_columns
            else:
                st.error(f"❌ Il foglio ha solo {len(df_transactions.columns)} colonne, ne servono 10")
                st.stop()
            
            # Converti date
            df_transactions['Data'] = pd.to_datetime(
                df_transactions['Data'],
                format='%d/%m/%Y',
                errors='coerce'
            )
            df_transactions = df_transactions.dropna(subset=['Data'])
            df_transactions = df_transactions.sort_values('Data', ascending=False).reset_index(drop=True)
            
            st.success(f"✅ {len(df_transactions)} transazioni caricate!")
            
            # Filtri sidebar
            st.sidebar.markdown("---")
            st.sidebar.markdown("### 🔍 Filtri")
            
            operazioni_uniche = df_transactions['Operazione'].dropna().unique().tolist()
            operazione_filter = st.sidebar.multiselect(
                "Tipo Operazione",
                options=operazioni_uniche,
                default=operazioni_uniche
            )
            
            strumenti_unici = sorted(df_transactions['Strumento'].dropna().unique().tolist())
            strumento_filter = st.sidebar.multiselect(
                "Strumento",
                options=strumenti_unici,
                default=[]
            )
            
            valute_uniche = sorted(df_transactions['Valuta'].dropna().unique().tolist())
            valuta_filter = st.sidebar.multiselect(
                "Valuta",
                options=valute_uniche,
                default=[]
            )
            
            # Filtro data
            min_date = df_transactions['Data'].min().date()
            max_date = df_transactions['Data'].max().date()
            date_range = st.sidebar.date_input(
                "Intervallo Date",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )
            
            # Applica filtri
            df_filtered = df_transactions.copy()
            
            if operazione_filter:
                df_filtered = df_filtered[df_filtered['Operazione'].isin(operazione_filter)]
            
            if strumento_filter:
                df_filtered = df_filtered[df_filtered['Strumento'].isin(strumento_filter)]
            
            if valuta_filter:
                df_filtered = df_filtered[df_filtered['Valuta'].isin(valuta_filter)]
            
            if len(date_range) == 2:
                start_date, end_date = date_range
                df_filtered = df_filtered[
                    (df_filtered['Data'].dt.date >= start_date) &
                    (df_filtered['Data'].dt.date <= end_date)
                ]
            
            df_filtered = df_filtered.sort_values('Data', ascending=False).reset_index(drop=True)
            
            # Tabella
            st.markdown("---")
            st.subheader("📋 DETTAGLIO TRANSAZIONI")
            
            df_display = df_filtered.copy()
            df_display['Data'] = df_display['Data'].dt.strftime('%d/%m/%Y')
            
            st.dataframe(
                df_display[expected_columns],
                use_container_width=True,
                height=500,
                hide_index=True
            )
            
            # Export
            st.markdown("---")
            csv = df_display.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Scarica Transazioni Filtrate (CSV)",
                data=csv,
                file_name=f"transazioni_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        except Exception as e:
            st.error(f"❌ Errore nel caricamento: {str(e)}")
            with st.expander("🔍 Dettagli errore"):
                st.code(str(e))
    
    # ==================== TAB 2: AGGIUNGI ====================
    with tab2:
        st.subheader("➕ Aggiungi Nuova Transazione")
        st.markdown("---")
        
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
        
        # Valori defaults
        default_operazioni = ["Buy", "Sell", "Bonifico", "Prelievo"]
        default_valute = ["EUR", "USD", "GBP", "CHF", "JPY", "CNH", "AUD", "CAD", "NZD", "SEK"]
        
        operazioni_options = sorted(list(set(existing_operazioni + default_operazioni)))
        valute_options = sorted(list(set(existing_valute + default_valute)))
        
        # ==================== FORM ====================
        with st.form("new_transaction_form", clear_on_submit=True):
            st.markdown("### 📝 Dettagli Transazione")
            
            col1, col2 = st.columns(2)
            
            with col1:
                data_input = st.date_input(
                    "Data *",
                    value=datetime.now(),
                    help="Data della transazione"
                )
                
                operazione_input = st.selectbox(
                    "Operazione *",
                    options=operazioni_options,
                    help="Tipo di operazione"
                )
                
                is_bonifico_prelievo = operazione_input in ["Bonifico", "Prelievo"]

                strumento_input = st.text_input(
                    "Strumento *",
                    value="CASH" if is_bonifico_prelievo else "",
                    placeholder="Es: BIT:LDO, NASDAQ:AAPL",
                    help="Ticker dello strumento",
                    disabled=is_bonifico_prelievo
                )
                
                nome_strumento = st.text_input(
                    "Nome Strumento",
                    value="Contanti" if is_bonifico_prelievo else "",
                    placeholder="Es: Apple Inc.",
                    help="Nome leggibile (opzionale)",
                    disabled=is_bonifico_prelievo
                )
                
                pmc_input = st.number_input(
                    "PMC (Prezzo Medio) *",
                    value=1.0 if is_bonifico_prelievo else 0.01,
                    step=0.01,
                    format="%.4f",
                    help="Prezzo medio di carico"
                )
                
                quantita_input = st.number_input(
                    "Quantità *",
                    value=0.01,
                    step=0.01,
                    format="%.4f",
                    help="Quantità acquistata"
                )
            
            with col2:
                lungo_breve = st.selectbox(
                    "Posizione",
                    options=["", "L", "B", "P"],
                    index=3 if is_bonifico_prelievo else 0,
                    format_func=lambda x: {
                        "": "Non specificato",
                        "L": "L - Lungo termine",
                        "B": "B - Breve termine",
                        "P": "P - Passività",
                    }[x],
                    help="Orizzonte temporale"
                )
                
                valuta_input = st.selectbox(
                    "Valuta *",
                    options=valute_options,
                    index=valute_options.index("EUR") if "EUR" in valute_options and is_bonifico_prelievo else 0,
                    help="Valuta della transazione"
                )
                
                tasso_cambio_input = st.number_input(
                    "Tasso di Cambio *",
                    min_value=0.0001,
                    value=1.0,
                    step=0.0001,
                    format="%.4f",
                    help="Tasso di cambio verso EUR (1.0 se EUR)"
                )
                
                commissioni_input = st.number_input(
                    "Commissioni",
                    value=0.0,
                    step=0.01,
                    format="%.2f",
                    help="Costi di intermediazione"
                )
            
            if is_bonifico_prelievo:
                st.info(f"💡 **{operazione_input}**: Strumento = CASH, PMC = 1.0, Posizione = P")
            
            st.markdown("---")
            st.markdown("### 📊 Riepilogo Calcoli")
            
            # Calcoli automatici
            totale_calcolato = pmc_input * quantita_input
            controvalore_calcolato = totale_calcolato / tasso_cambio_input if tasso_cambio_input > 0 else 0
            
            col_calc1, col_calc2 = st.columns(2)
            
            with col_calc1:
                st.metric(
                    label=f"Totale (in {valuta_input})",
                    value=f"{totale_calcolato:,.2f}",
                    help="PMC × Quantità"
                )
            
            with col_calc2:
                st.metric(
                    label="Controvalore €",
                    value=f"€{controvalore_calcolato:,.2f}",
                    help="Totale ÷ Tasso Cambio"
                )
            
            st.markdown("---")
            
            # Bottoni DENTRO IL FORM
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
        
        # ==================== GESTIONE SUBMIT (FUORI DAL FORM) ====================
        if submitted:
            errors = []
            
            if not strumento_input.strip():
                errors.append("⚠️ Il campo 'Strumento' è obbligatorio")
            
            if pmc_input <= 0:
                errors.append("⚠️ Il 'PMC' deve essere > 0")
            
            if quantita_input <= 0:
                errors.append("⚠️ La 'Quantità' deve essere > 0")
            
            if tasso_cambio_input <= 0:
                errors.append("⚠️ Il 'Tasso di Cambio' deve essere > 0")
            
            if errors:
                for error in errors:
                    st.error(error)
            else:
                new_transaction = {
                    'Data': data_input.strftime('%d/%m/%Y'),
                    'Operazione': operazione_input.strip(),
                    'Strumento': str(strumento_input).upper().strip(),
                    'PMC': float(pmc_input),
                    'Quantita': float(quantita_input),
                    'Totale': float(totale_calcolato),
                    'Valuta': valuta_input,
                    'Tasso_cambio': float(tasso_cambio_input),
                    'Commissioni': float(commissioni_input),
                    'Controvalore': float(controvalore_calcolato),
                    'Lungo_breve': lungo_breve,
                    'Nome_strumento': nome_strumento.strip()
                }
                
                with st.spinner("💾 Salvataggio transazione..."):
                    success, message = append_transaction_via_webhook(new_transaction, WEBHOOK_URL)
                
                if success:
                    st.success(f"✅ {message}")
                    st.balloons()
                    
                    st.markdown("### 👀 Transazione Salvata")
                    df_preview = pd.DataFrame([new_transaction])
                    st.dataframe(df_preview, use_container_width=True, hide_index=True)
                    
                    st.cache_data.clear()
                    st.info("🔄 Torna a 'Visualizza Transazioni' e clicca 'Aggiorna'")
                else:
                    st.error(f"❌ {message}")
                    st.warning("Verifica che l'URL del webhook sia corretto.")
                    
                    df_preview = pd.DataFrame([new_transaction])
                    csv_backup = df_preview.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Scarica Backup CSV",
                        data=csv_backup,
                        file_name=f"transazione_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
        
        with st.expander("💡 Suggerimenti"):
            st.markdown("""
            - **PMC**: Prezzo unitario di acquisto/vendita
            - **Quantità**: Numero di unità
            - **Tasso Cambio**: Se EUR metti 1.0, altrimenti il cambio EUR/VALUTA
            - **Totale e Controvalore**: Calcolati automaticamente
            """)


    # ==================== TAB 3: CONFIGURAZIONE ====================
    with tab3:
        st.subheader("⚙️ Configurazione Webhook")
        st.markdown("---")
        
        st.info(f"""
        **URL Webhook Attualmente Configurato:**
        
        ```
        {WEBHOOK_URL}
        ```
        
        Se questo URL non è corretto, il form non funzionerà!
        """)
        
        st.markdown("### 📋 Come Configurare")
        st.markdown("""
        1. Apri il tuo Google Sheet
        2. Vai su **Extensions** → **Apps Script**
        3. Incolla il codice Google Apps Script
        4. Clicca **Deploy** → **New Deployment** → **Web App**
        5. Copia l'URL generato
        6. Incolla qui sotto nel codice Python
        """)
        
        # Test webhook
        st.markdown("---")
        st.markdown("### 🧪 Test Webhook")
        
        if st.button("🧪 Testa Connessione", use_container_width=True):
            with st.spinner("Testing..."):
                try:
                    response = requests.get(WEBHOOK_URL, timeout=10)
                    if response.status_code == 200:
                        st.success("✅ Webhook raggiungibile!")
                        st.json(response.json())
                    else:
                        st.error(f"❌ HTTP {response.status_code}")
                except Exception as e:
                    st.error(f"❌ Errore: {str(e)}")


if __name__ == "__transaction_tracker_app__":
    transaction_tracker_app()
