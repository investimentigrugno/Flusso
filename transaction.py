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
        # Funzione per convertire numeri con virgola
        def format_decimal(value):
            """Converte numero in stringa con virgola come separatore decimale"""
            if isinstance(value, str):
                # Già stringa, sostituisci punto con virgola
                return value.replace('.', ',')
            elif isinstance(value, (int, float)):
                # Converti numero in stringa con virgola
                return str(value).replace('.', ',')
            return value
        
        # Prepara i dati per il webhook con virgole come separatore
        payload = {
            "data": transaction_data['Data'],
            "operazione": transaction_data['Operazione'],
            "strumento": transaction_data['Strumento'],
            "pmc": format_decimal(transaction_data['PMC']),
            "quantita": format_decimal(transaction_data['Quantità']),
            "totale": format_decimal(transaction_data['Totale']),
            "valuta": transaction_data['Valuta'],
            "tasso_cambio": format_decimal(transaction_data['Tasso di cambio']),
            "commissioni": format_decimal(transaction_data['Commissioni']),
            "controvalore": format_decimal(transaction_data['Controvalore €'])
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
    
    st.title("💼 Transaction Tracker")
    st.markdown("---")
    
    # URL del webhook
    WEBHOOK_URL = "https://script.google.com/macros/s/TUO_WEBHOOK_URL/exec"
    
    # ==================== FORM ====================
    with st.form("transaction_form", clear_on_submit=False):
        st.markdown("### 📝 Dettagli Transazione")
        
        col1, col2 = st.columns(2)
        
        with col1:
            operazioneinput = st.selectbox(
                "Operazione *",
                options=["ACQUISTO", "VENDITA"],
                help="Tipo di operazione"
            )
            
            strumentoinput = st.text_input(
                "Strumento (Ticker) *",
                placeholder="Es: AAPL, BTC-USD, BIT:ENI",
                help="Inserisci il ticker dello strumento"
            )
            
            nomestrumento = st.text_input(
                "Nome Strumento",
                placeholder="Es: Apple Inc., Bitcoin",
                help="Nome leggibile dello strumento (opzionale)"
            )
            
            quantitainput = st.number_input(
                "Quantità *",
                min_value=0.0001,
                value=1.0,
                step=0.01,
                format="%.4f",
                help="Quantità da acquistare/vendere"
            )
            
            pmcinput = st.number_input(
                "Prezzo (PMC) *",
                min_value=0.01,
                value=100.0,
                step=0.01,
                format="%.2f",
                help="Prezzo medio di carico"
            )
        
        with col2:
            lungobreve = st.selectbox(
                "Posizione",
                options=["", "L", "B"],
                format_func=lambda x: {
                    "": "Non specificato",
                    "L": "L - Lungo termine",
                    "B": "B - Breve termine"
                }[x],
                help="Orizzonte temporale della posizione"
            )
            
            valutainput = st.selectbox(
                "Valuta *",
                options=["EUR", "USD", "GBP", "JPY", "CHF"],
                help="Valuta dello strumento"
            )
            
            tassocambioinput = st.number_input(
                "Tasso di Cambio",
                min_value=0.01,
                value=1.0,
                step=0.01,
                format="%.4f",
                help="Tasso di cambio vs EUR (1.0 se EUR)"
            )
            
            commissioniinput = st.number_input(
                "Commissioni",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.2f",
                help="Commissioni della transazione"
            )
            
            datainput = st.date_input(
                "Data",
                value=datetime.now(),
                help="Data della transazione"
            )
        
        st.markdown("---")
        
        # Bottone submit
        submitted = st.form_submit_button("💾 Salva Transazione", type="primary", use_container_width=True)
    
    # ⭐ ELABORAZIONE FUORI DAL FORM (dopo il submit) ⭐
    if submitted:
        # ==================== VALIDAZIONE ====================
        errors = []
        
        if not strumentoinput or strumentoinput.strip() == "":
            errors.append("⚠️ Il campo 'Strumento' è obbligatorio")
        if pmcinput <= 0:
            errors.append("⚠️ Il PMC deve essere maggiore di 0")
        if quantitainput <= 0:
            errors.append("⚠️ La Quantità deve essere maggiore di 0")
        if tassocambioinput <= 0:
            errors.append("⚠️ Il Tasso di Cambio deve essere maggiore di 0")
        
        if errors:
            for error in errors:
                st.error(error)
        else:
            # ==================== CALCOLI ====================
            totalecalcolato = pmcinput * quantitainput
            controvalorecalcolato = totalecalcolato / tassocambioinput
            
            # Mostra calcoli
            st.markdown("### 📊 Riepilogo Calcoli")
            colcalc1, colcalc2 = st.columns(2)
            with colcalc1:
                st.metric(
                    label=f"Totale (in {valutainput})", 
                    value=f"{totalecalcolato:,.2f}"
                )
            with colcalc2:
                st.metric(
                    label="Controvalore (EUR)", 
                    value=f"€{controvalorecalcolato:,.2f}"
                )
            
            st.markdown("---")
            
            # ⭐ PREPARA PAYLOAD ⭐
            payload = {
                "data": datainput.strftime('%d/%m/%Y %H.%M.%S'),
                "operazione": operazioneinput,
                "strumento": strumentoinput.upper().strip(),
                "pmc": pmcinput,
                "quantita": quantitainput,
                "totale": totalecalcolato,
                "valuta": valutainput,
                "tasso_cambio": tassocambioinput,
                "commissioni": commissioniinput,
                "controvalore": controvalorecalcolato,
                "lungo_breve": lungobreve,
                "nome_strumento": nomestrumento if nomestrumento else strumentoinput.upper()
            }
            
            # ⭐ INVIA AL WEBHOOK ⭐
            with st.spinner("💾 Salvataggio transazione in corso..."):
                try:
                    response = requests.post(
                        WEBHOOK_URL,
                        json=payload,
                        headers={'Content-Type': 'application/json'},
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        try:
                            result = response.json()
                            
                            if result.get('success'):
                                st.success(f"✅ {result.get('message')}")
                                st.balloons()
                                
                                # Mostra riepilogo
                                st.markdown("### 👀 Transazione Salvata")
                                
                                col_recap1, col_recap2, col_recap3 = st.columns(3)
                                
                                with col_recap1:
                                    st.write(f"**Operazione:** {operazioneinput}")
                                    st.write(f"**Strumento:** {strumentoinput.upper()}")
                                    st.write(f"**Nome:** {nomestrumento if nomestrumento else '-'}")
                                
                                with col_recap2:
                                    st.write(f"**Quantità:** {quantitainput}")
                                    st.write(f"**Prezzo:** {pmcinput} {valutainput}")
                                    st.write(f"**Posizione:** {lungobreve if lungobreve else '-'}")
                                
                                with col_recap3:
                                    st.write(f"**Totale:** {totalecalcolato:,.2f} {valutainput}")
                                    st.write(f"**Controvalore:** €{controvalorecalcolato:,.2f}")
                                    st.write(f"**Commissioni:** €{commissioniinput:,.2f}")
                            else:
                                st.error(f"❌ {result.get('message')}")
                        
                        except Exception as json_error:
                            st.warning("⚠️ Risposta non standard, ma transazione probabilmente salvata")
                            st.info("🔍 Controlla il foglio Google Sheets")
                    
                    else:
                        st.error(f"❌ Errore HTTP {response.status_code}")
                
                except requests.exceptions.Timeout:
                    st.error("❌ Timeout: il server non ha risposto entro 30 secondi")
                    st.warning("⚠️ La transazione potrebbe essere stata salvata comunque")
                
                except requests.exceptions.ConnectionError:
                    st.error("❌ Errore di connessione: verifica l'URL del webhook")
                
                except Exception as e:
                    st.error(f"❌ Errore imprevisto: {str(e)}")

        # Suggerimenti
        with st.expander("💡 Suggerimenti per compilare il form"):
            st.markdown("""
            - **Data**: Seleziona la data effettiva della transazione
            - **Operazione**: Scegli Buy, Sell, Bonifico O Prelievo
            - **Strumento**: Inserisci il ticker corretto presente su Google Finance
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
