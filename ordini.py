import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests

# Configurazione pagina
st.set_page_config(
    page_title="Gestione Ordini",
    page_icon="📦",
    layout="wide"
)

@st.cache_data(ttl=120)
def load_sheet_csv_proposte(spreadsheet_id, gid):
    """Carica foglio pubblico via CSV export"""
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    
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


@st.cache_data(ttl=120)
def load_sheet_csv_ordini(spreadsheet_id, gid):
    """Carica foglio Ordini pubblico via CSV export"""
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    
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


def aggiorna_stato_ordine_via_webhook(row_number, stato_esecuzione, data_esecuzione, webhook_url):
    """Aggiorna lo stato di esecuzione di un ordine via webhook"""
    try:
        payload = {
            "action": "update_stato_ordine",
            "row_number": row_number,
            "stato_esecuzione": stato_esecuzione,
            "data_esecuzione": data_esecuzione
        }
        
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
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


def copia_proposta_in_ordini_via_webhook(proposta_data, webhook_url):
    """Copia una proposta approvata nel foglio Ordini via webhook"""
    try:
        payload = {
            "action": "copia_proposta_in_ordini",
            "data_proposta": proposta_data['DATA'],
            "responsabile": proposta_data['RESPONSABILE'],
            "operazione": proposta_data['OPERAZIONE'],
            "strumento": proposta_data['STRUMENTO'],
            "quantita": proposta_data['QUANTITA'],
            "pmc": proposta_data['PMC'],
            "sl": proposta_data['SL'],
            "tp": proposta_data['TP'],
            "valuta": proposta_data['VALUTA'],
            "esito": proposta_data['ESITO'],
            "stato_esecuzione": "In Attesa",
            "data_esecuzione": ""
        }
        
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('success', False), result.get('message', 'Risposta sconosciuta')
        else:
            return False, f"Errore HTTP {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, f"Errore imprevisto: {str(e)}"


def ordini_app():
    """Applicazione Gestione Ordini da Proposte Approvate"""
    
    st.title("📦 Gestione Ordini da Proposte Approvate")
    st.markdown("Gestisci lo stato di esecuzione degli ordini derivanti dalle proposte approvate (ESITO ≥ 3)")
    st.markdown("---")
    
    # ==================== CONFIGURAZIONE ====================
    # Foglio Proposte
    spreadsheet_id_proposte = "1WEt_YQCASRr5EWFk77DbBI6DcOIw2ifRIMlzAaG58uY"
    gid_proposte = "836776830"
    
    # Foglio Ordini
    spreadsheet_id_ordini = "1mD9jxDJv26aZwCdIbvQVjlJGBhRwKWwQnPpPPq0ON5Y"
    gid_ordini = "1901209178"
    
    # Webhook URL
    WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbwPSIjUt9gAYh0EY1vuoqEgyqQTSxxUrQgjGZqGrOFx4BWDeWbZCwcThGlivJsHznkD/exec"
    
    # ==================== SIDEBAR ====================
    st.sidebar.markdown("### ⚙️ Opzioni Ordini")
    
    # Bottone refresh
    if st.sidebar.button("🔄 Aggiorna Ordini", type="primary"):
        st.cache_data.clear()
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.caption("💡 I dati vengono aggiornati automaticamente ogni 2 minuti")
    
    # ==================== TABS ====================
    tab1, tab2 = st.tabs(["📋 Ordini Attivi", "➕ Importa da Proposte"])
    
    # ==================== TAB 1: ORDINI ATTIVI ====================
    with tab1:
        try:
            with st.spinner("Caricamento ordini dal Google Sheet..."):
                df_ordini = load_sheet_csv_ordini(spreadsheet_id_ordini, gid_ordini)
            
            if df_ordini is None or df_ordini.empty:
                st.warning("⚠️ Il foglio Ordini è vuoto o non accessibile")
                st.info("💡 Vai al tab 'Importa da Proposte' per aggiungere ordini")
                st.stop()
            
            # Pulizia dati
            # Rimuovi righe completamente vuote
            df_ordini = df_ordini.dropna(how='all')
            
            # Aggiungi ROW_NUMBER per identificare le righe
            df_ordini['ROW_NUMBER'] = range(2, len(df_ordini) + 2)
            
            # Converti date se presenti
            if 'DATA PROPOSTA' in df_ordini.columns:
                df_ordini['DATA PROPOSTA'] = pd.to_datetime(
                    df_ordini['DATA PROPOSTA'],
                    format='%d/%m/%Y',
                    errors='coerce',
                    dayfirst=True
                )
            
            if 'DATA ESECUZIONE' in df_ordini.columns:
                df_ordini['DATA ESECUZIONE'] = pd.to_datetime(
                    df_ordini['DATA ESECUZIONE'],
                    format='%d/%m/%Y',
                    errors='coerce',
                    dayfirst=True
                )
            
            # Gestisci STATO ESECUZIONE
            if 'STATO ESECUZIONE' not in df_ordini.columns:
                df_ordini['STATO ESECUZIONE'] = 'In Attesa'
            else:
                df_ordini['STATO ESECUZIONE'] = df_ordini['STATO ESECUZIONE'].fillna('In Attesa')
                df_ordini['STATO ESECUZIONE'] = df_ordini['STATO ESECUZIONE'].replace('', 'In Attesa')
            
            # Ordina per data decrescente
            if 'DATA PROPOSTA' in df_ordini.columns:
                df_ordini = df_ordini.sort_values('DATA PROPOSTA', ascending=False, na_position='last')
            
            df_ordini = df_ordini.reset_index(drop=True)
            
            # ==================== STATISTICHE ====================
            totali = len(df_ordini)
            in_attesa = len(df_ordini[df_ordini['STATO ESECUZIONE'] == 'In Attesa'])
            eseguiti = len(df_ordini[df_ordini['STATO ESECUZIONE'] == 'Eseguito'])
            
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            
            with col_stat1:
                st.metric("📊 Totale Ordini", totali)
            
            with col_stat2:
                st.metric("⏳ In Attesa", in_attesa)
            
            with col_stat3:
                st.metric("✅ Eseguiti", eseguiti)
            
            st.markdown("---")
            
            # ==================== FILTRI SIDEBAR ====================
            st.sidebar.markdown("---")
            st.sidebar.markdown("### 🔍 Filtri")
            
            filtro_stato = st.sidebar.radio(
                "Filtra per stato:",
                options=["Tutti", "In Attesa", "Eseguito"],
                format_func=lambda x: f"{x} ({totali if x == 'Tutti' else in_attesa if x == 'In Attesa' else eseguiti})"
            )
            
            # Filtro per responsabile se la colonna esiste
            if 'RESPONSABILE' in df_ordini.columns:
                responsabili_unici = []
                for resp in df_ordini['RESPONSABILE'].dropna().unique():
                    if isinstance(resp, str):
                        responsabili_unici.extend([r.strip() for r in resp.replace(',', ' ').split()])
                responsabili_unici = sorted(list(set(responsabili_unici)))
                
                responsabile_filter = st.sidebar.multiselect(
                    "Filtra per Responsabile",
                    options=responsabili_unici,
                    default=[]
                )
            else:
                responsabile_filter = []
            
            # Applica filtri
            df_filtrato = df_ordini.copy()
            
            if filtro_stato != "Tutti":
                df_filtrato = df_filtrato[df_filtrato['STATO ESECUZIONE'] == filtro_stato]
            
            if responsabile_filter and 'RESPONSABILE' in df_filtrato.columns:
                df_filtrato = df_filtrato[
                    df_filtrato['RESPONSABILE'].apply(
                        lambda x: any(r in str(x) for r in responsabile_filter) if pd.notna(x) else False
                    )
                ]
            
            # ==================== GRAFICO DISTRIBUZIONE ====================
            if totali > 0:
                st.subheader("📊 Distribuzione Ordini per Stato")
                
                stato_counts = df_ordini['STATO ESECUZIONE'].value_counts()
                
                fig_stato = px.pie(
                    values=stato_counts.values,
                    names=stato_counts.index,
                    color=stato_counts.index,
                    color_discrete_map={'In Attesa': '#FFA500', 'Eseguito': '#2ecc71'},
                    hole=0.4
                )
                
                fig_stato.update_traces(
                    textposition='inside',
                    textinfo='percent+label',
                    textfont_size=14
                )
                
                fig_stato.update_layout(
                    plot_bgcolor='#0e1117',
                    paper_bgcolor='#0e1117',
                    font={'color': 'white', 'size': 12},
                    height=350,
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
                )
                
                st.plotly_chart(fig_stato, use_container_width=True)
                st.markdown("---")
            
            # ==================== LISTA ORDINI ====================
            st.subheader(f"📋 Lista Ordini - {filtro_stato}")
            
            if df_filtrato.empty:
                st.info(f"Nessun ordine con stato '{filtro_stato}'")
            else:
                st.caption(f"🔽 Mostrando {len(df_filtrato)} ordini")
                
                # Visualizza ogni ordine come card
                for idx, ordine in df_filtrato.iterrows():
                    original_row_number = ordine['ROW_NUMBER']
                    
                    # Badge operazione
                    if 'OPERAZIONE' in ordine:
                        op_color = "🟢" if ordine['OPERAZIONE'] == 'Buy' else "🔴"
                    else:
                        op_color = "⚪"
                    
                    with st.container():
                        col_header, col_stato_badge = st.columns([4, 1])
                        
                        with col_header:
                            strumento = ordine.get('STRUMENTO', 'N/A')
                            operazione = ordine.get('OPERAZIONE', 'N/A')
                            st.markdown(f"### {op_color} {strumento} - {operazione}")
                        
                        with col_stato_badge:
                            stato_attuale = ordine['STATO ESECUZIONE']
                            if stato_attuale == 'Eseguito':
                                st.success("✅ Eseguito")
                            else:
                                st.warning("⏳ In Attesa")
                        
                        # Dettagli ordine
                        col_det1, col_det2, col_det3, col_det4 = st.columns(4)
                        
                        with col_det1:
                            if 'RESPONSABILE' in ordine:
                                st.markdown(f"**Responsabile:** {ordine['RESPONSABILE']}")
                            if 'ESITO' in ordine and pd.notna(ordine['ESITO']):
                                st.markdown(f"**Esito:** {ordine['ESITO']}/5")
                        
                        with col_det2:
                            if 'QUANTITA' in ordine:
                                st.markdown(f"**Quantità:** {ordine['QUANTITA']}")
                            if 'PMC' in ordine and 'VALUTA' in ordine:
                                st.markdown(f"**PMC:** {ordine['PMC']} {ordine['VALUTA']}")
                        
                        with col_det3:
                            if 'SL' in ordine:
                                st.markdown(f"**SL:** {ordine['SL'] if pd.notna(ordine['SL']) and ordine['SL'] != '' else 'N/A'}")
                            if 'TP' in ordine:
                                st.markdown(f"**TP:** {ordine['TP'] if pd.notna(ordine['TP']) and ordine['TP'] != '' else 'N/A'}")
                        
                        with col_det4:
                            if 'DATA PROPOSTA' in ordine and pd.notna(ordine['DATA PROPOSTA']):
                                st.markdown(f"**Data Proposta:** {ordine['DATA PROPOSTA'].strftime('%d/%m/%Y')}")
                            
                            if 'DATA ESECUZIONE' in ordine and pd.notna(ordine['DATA ESECUZIONE']):
                                st.markdown(f"**Data Esecuzione:** {ordine['DATA ESECUZIONE'].strftime('%d/%m/%Y')}")
                        
                        # Azioni
                        col_azioni1, col_azioni2, col_azioni3 = st.columns([1, 1, 3])
                        
                        with col_azioni1:
                            if stato_attuale != 'Eseguito':
                                if st.button("✅ Segna Eseguito", key=f"esegui_{original_row_number}", use_container_width=True):
                                    data_esecuzione = datetime.now().strftime('%d/%m/%Y')
                                    with st.spinner("⏳ Aggiornamento in corso..."):
                                        success, message = aggiorna_stato_ordine_via_webhook(
                                            original_row_number,
                                            'Eseguito',
                                            data_esecuzione,
                                            WEBHOOK_URL
                                        )
                                    if success:
                                        st.success(f"✅ {message}")
                                        st.cache_data.clear()
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {message}")
                        
                        with col_azioni2:
                            if stato_attuale == 'Eseguito':
                                if st.button("⏳ Riporta in Attesa", key=f"attesa_{original_row_number}", use_container_width=True):
                                    with st.spinner("⏳ Aggiornamento in corso..."):
                                        success, message = aggiorna_stato_ordine_via_webhook(
                                            original_row_number,
                                            'In Attesa',
                                            '',
                                            WEBHOOK_URL
                                        )
                                    if success:
                                        st.success(f"✅ {message}")
                                        st.cache_data.clear()
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {message}")
                        
                        st.markdown("---")
                
                # ==================== TABELLA RIASSUNTIVA ====================
                with st.expander("📊 Visualizza Tabella Completa Ordini"):
                    df_display = df_filtrato.copy()
                    
                    if 'DATA PROPOSTA' in df_display.columns:
                        df_display['DATA PROPOSTA'] = df_display['DATA PROPOSTA'].apply(
                            lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else ''
                        )
                    
                    if 'DATA ESECUZIONE' in df_display.columns:
                        df_display['DATA ESECUZIONE'] = df_display['DATA ESECUZIONE'].apply(
                            lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else ''
                        )
                    
                    # Nascondi ROW_NUMBER
                    colonne_da_nascondere = ['ROW_NUMBER']
                    colonne_disponibili = [col for col in df_display.columns if col not in colonne_da_nascondere]
                    
                    def color_stato(val):
                        if val == 'Eseguito':
                            return 'background-color: #2ecc71; color: white; font-weight: bold'
                        elif val == 'In Attesa':
                            return 'background-color: #FFA500; color: white; font-weight: bold'
                        return ''
                    
                    if 'STATO ESECUZIONE' in colonne_disponibili:
                        styled_df = df_display[colonne_disponibili].style.map(color_stato, subset=['STATO ESECUZIONE'])
                    else:
                        styled_df = df_display[colonne_disponibili]
                    
                    st.dataframe(styled_df, use_container_width=True, height=400, hide_index=True)
                
                # ==================== EXPORT CSV ====================
                st.markdown("---")
                csv = df_display[colonne_disponibili].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Scarica Ordini (CSV)",
                    data=csv,
                    file_name=f"ordini_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        except Exception as e:
            st.error(f"❌ Errore nel caricamento ordini: {str(e)}")
            st.info("💡 Verifica che il foglio Ordini sia condiviso pubblicamente")
    
    # ==================== TAB 2: IMPORTA DA PROPOSTE ====================
    with tab2:
        st.subheader("➕ Importa Proposte Approvate nel Foglio Ordini")
        st.markdown("Seleziona le proposte approvate (ESITO ≥ 3) da copiare nel foglio Ordini")
        st.markdown("---")
        
        try:
            with st.spinner("Caricamento proposte approvate..."):
                df_proposte = load_sheet_csv_proposte(spreadsheet_id_proposte, gid_proposte)
            
            if df_proposte is None or df_proposte.empty:
                st.error("❌ Impossibile caricare il foglio Proposte")
                st.stop()
            
            # Definisci colonne attese
            expected_columns = [
                'DATA', 'RESPONSABILE', 'OPERAZIONE', 'STRUMENTO', 'QUANTITA',
                'PMC', 'SL', 'TP', 'ORIZZONTE TEMPORALE', 'ALLEGATO',
                'MOTIVAZIONE', 'LINK', 'IMMAGINE', 'VALUTA', 'ESITO',
                'GALLOZ', 'STE', 'GARGIU', 'ALE', 'GIACA'
            ]
            
            if len(df_proposte.columns) >= 20:
                df_proposte.columns = expected_columns[:len(df_proposte.columns)]
            
            # Aggiungi ROW_NUMBER
            df_proposte['ROW_NUMBER'] = range(2, len(df_proposte) + 2)
            
            # Converti date
            df_proposte['DATA'] = df_proposte['DATA'].astype(str).str.replace(
                r'(\d{2})\.(\d{2})\.(\d{2})',
                r'\1:\2:\3',
                regex=True
            )
            
            df_proposte['DATA'] = pd.to_datetime(
                df_proposte['DATA'],
                format='%d/%m/%Y %H:%M:%S',
                errors='coerce',
                dayfirst=True
            )
            
            # Converti ESITO in numerico
            df_proposte['ESITO'] = pd.to_numeric(df_proposte['ESITO'], errors='coerce').astype('Int64')
            
            # Filtra proposte approvate
            df_approvate = df_proposte[df_proposte['ESITO'] >= 3].copy()
            
            if df_approvate.empty:
                st.warning("⚠️ Nessuna proposta approvata trovata (ESITO ≥ 3)")
                st.stop()
            
            df_approvate = df_approvate.sort_values('DATA', ascending=False).reset_index(drop=True)
            
            st.success(f"✅ {len(df_approvate)} proposte approvate disponibili per l'importazione")
            
            # Mostra proposte
            for idx, proposta in df_approvate.iterrows():
                with st.expander(f"🔹 {proposta['STRUMENTO']} - {proposta['OPERAZIONE']} (Esito: {proposta['ESITO']}/5)"):
                    
                    col_info1, col_info2, col_info3 = st.columns(3)
                    
                    with col_info1:
                        st.write(f"**Responsabile:** {proposta['RESPONSABILE']}")
                        st.write(f"**Quantità:** {proposta['QUANTITA']}")
                    
                    with col_info2:
                        st.write(f"**PMC:** {proposta['PMC']} {proposta['VALUTA']}")
                        st.write(f"**Esito:** {proposta['ESITO']}/5")
                    
                    with col_info3:
                        data_str = proposta['DATA'].strftime('%d/%m/%Y') if pd.notna(proposta['DATA']) else 'N/A'
                        st.write(f"**Data:** {data_str}")
                    
                    if st.button(f"📋 Copia in Ordini", key=f"copia_{proposta['ROW_NUMBER']}", use_container_width=True):
                        proposta_dict = {
                            'DATA': proposta['DATA'].strftime('%d/%m/%Y') if pd.notna(proposta['DATA']) else '',
                            'RESPONSABILE': proposta['RESPONSABILE'],
                            'OPERAZIONE': proposta['OPERAZIONE'],
                            'STRUMENTO': proposta['STRUMENTO'],
                            'QUANTITA': proposta['QUANTITA'],
                            'PMC': proposta['PMC'],
                            'SL': proposta['SL'],
                            'TP': proposta['TP'],
                            'VALUTA': proposta['VALUTA'],
                            'ESITO': int(proposta['ESITO'])
                        }
                        
                        with st.spinner("⏳ Copia in corso..."):
                            success, message = copia_proposta_in_ordini_via_webhook(proposta_dict, WEBHOOK_URL)
                        
                        if success:
                            st.success(f"✅ {message}")
                            st.cache_data.clear()
                            st.info("Vai al tab 'Ordini Attivi' e clicca 'Aggiorna Ordini'")
                        else:
                            st.error(f"❌ {message}")
        
        except Exception as e:
            st.error(f"❌ Errore: {str(e)}")

if __name__ == "__main__":
    ordini_app()
