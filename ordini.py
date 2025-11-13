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

# ==================== CONFIGURAZIONE ====================
SPREADSHEET_ID_PROPOSTE = "1WEt_YQCASRr5EWFk77DbBI6DcOIw2ifRIMlzAaG58uY"
GID_PROPOSTE = "836776830"

SPREADSHEET_ID_ORDINI = "1mD9jxDJv26aZwCdIbvQVjlJGBhRwKWwQnPpPPq0ON5Y"
GID_ORDINI = "1901209178"

WEBHOOK_URL_ORDINI = "TUO_WEBHOOK_URL_ORDINI_QUI"

# ==================== FUNZIONI CARICAMENTO DATI ====================
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
    """Aggiorna lo stato di un ordine (Attivo -> Eseguito o Cancellato)"""
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
            
    except Exception as e:
        return False, f"Errore imprevisto: {str(e)}"


# ==================== FUNZIONE CALCOLO LIQUIDITÀ ====================
def calcola_liquidita_disponibile(df_ordini, liquidita_totale):
    """
    Calcola: Liquidità Disponibile = Liquidità Totale - Valore Totale Ordini Attivi
    
    Returns:
        dict: {
            'liquidita_totale': float,
            'valore_ordini_attivi': float,
            'liquidita_disponibile': float,
            'num_ordini_attivi': int
        }
    """
    if df_ordini is None or df_ordini.empty:
        return {
            'liquidita_totale': liquidita_totale,
            'valore_ordini_attivi': 0.0,
            'liquidita_disponibile': liquidita_totale,
            'num_ordini_attivi': 0
        }
    
    # Filtra ordini attivi
    ordini_attivi = df_ordini[df_ordini['STATO ESECUZIONE'] == 'Attivo'].copy()
    
    # Calcola valore totale ordini attivi (QUANTITA * PMC)
    if 'QUANTITA' in ordini_attivi.columns and 'PMC' in ordini_attivi.columns:
        ordini_attivi['VALORE'] = pd.to_numeric(ordini_attivi['QUANTITA'], errors='coerce') * \
                                   pd.to_numeric(ordini_attivi['PMC'], errors='coerce')
        valore_ordini_attivi = ordini_attivi['VALORE'].sum()
    else:
        valore_ordini_attivi = 0.0
    
    liquidita_disponibile = liquidita_totale - valore_ordini_attivi
    
    return {
        'liquidita_totale': liquidita_totale,
        'valore_ordini_attivi': valore_ordini_attivi,
        'liquidita_disponibile': liquidita_disponibile,
        'num_ordini_attivi': len(ordini_attivi)
    }


# ==================== INIZIALIZZA SESSION STATE ====================
if 'liquidita_info' not in st.session_state:
    st.session_state.liquidita_info = None


def ordini_app():
    """Applicazione Gestione Ordini"""
    
    st.title("📦 Gestione Ordini")
    st.markdown("Monitora e gestisci gli ordini di trading approvati")
    st.markdown("---")
    
    # ==================== SIDEBAR ====================
    st.sidebar.markdown("### ⚙️ Opzioni")
    
    # Input liquidità totale
    st.sidebar.markdown("### 💰 Liquidità Portfolio")
    liquidita_totale = st.sidebar.number_input(
        "Liquidità Totale (€)",
        min_value=0.0,
        value=2228.92,
        step=100.0,
        format="%.2f",
        help="Inserisci la liquidità totale disponibile dal portfolio"
    )
    
    # Bottone refresh
    if st.sidebar.button("🔄 Aggiorna Dati", type="primary"):
        st.cache_data.clear()
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.caption("💡 I dati vengono aggiornati automaticamente ogni 2 minuti")
    st.sidebar.caption("🔗 Gli ordini approvati vengono importati automaticamente dal foglio Proposte")
    
    # ==================== CARICA DATI ====================
    try:
        with st.spinner("Caricamento ordini..."):
            df_ordini = load_sheet_csv_ordini(SPREADSHEET_ID_ORDINI, GID_ORDINI)
        
        if df_ordini is None or df_ordini.empty:
            st.warning("⚠️ Nessun ordine trovato")
            st.info("💡 Gli ordini approvati (ESITO ≥ 3) verranno importati automaticamente dal foglio Proposte")
            
            # Salva liquidità info anche se non ci sono ordini
            st.session_state.liquidita_info = calcola_liquidita_disponibile(None, liquidita_totale)
            st.stop()
        
        # Pulizia dati
        df_ordini = df_ordini.dropna(how='all')
        df_ordini['ROW_NUMBER'] = range(2, len(df_ordini) + 2)
        
        # Converti date
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
        
        # Gestisci STATO ESECUZIONE (default: Attivo)
        if 'STATO ESECUZIONE' not in df_ordini.columns:
            df_ordini['STATO ESECUZIONE'] = 'Attivo'
        else:
            df_ordini['STATO ESECUZIONE'] = df_ordini['STATO ESECUZIONE'].fillna('Attivo')
            df_ordini['STATO ESECUZIONE'] = df_ordini['STATO ESECUZIONE'].replace('', 'Attivo')
        
        # Ordina per data decrescente
        if 'DATA PROPOSTA' in df_ordini.columns:
            df_ordini = df_ordini.sort_values('DATA PROPOSTA', ascending=False, na_position='last')
        
        df_ordini = df_ordini.reset_index(drop=True)
        
        # ==================== CALCOLA LIQUIDITÀ ====================
        liquidita_info = calcola_liquidita_disponibile(df_ordini, liquidita_totale)
        st.session_state.liquidita_info = liquidita_info
        
        # ==================== METRICHE PRINCIPALI ====================
        col_met1, col_met2, col_met3, col_met4 = st.columns(4)
        
        with col_met1:
            st.metric(
                "💰 Liquidità Totale",
                f"€ {liquidita_info['liquidita_totale']:,.2f}"
            )
        
        with col_met2:
            st.metric(
                "📦 Valore Ordini Attivi",
                f"€ {liquidita_info['valore_ordini_attivi']:,.2f}",
                delta=f"{liquidita_info['num_ordini_attivi']} ordini"
            )
        
        with col_met3:
            st.metric(
                "✅ Liquidità Disponibile",
                f"€ {liquidita_info['liquidita_disponibile']:,.2f}",
                delta=f"{(liquidita_info['liquidita_disponibile']/liquidita_info['liquidita_totale']*100):.1f}%"
            )
        
        with col_met4:
            totali = len(df_ordini)
            attivi = len(df_ordini[df_ordini['STATO ESECUZIONE'] == 'Attivo'])
            eseguiti = len(df_ordini[df_ordini['STATO ESECUZIONE'] == 'Eseguito'])
            cancellati = len(df_ordini[df_ordini['STATO ESECUZIONE'] == 'Cancellato'])
            st.metric("📊 Totale Ordini", totali)
        
        st.markdown("---")
        
        # ==================== SEZIONE ORDINI ATTIVI (IN RISALTO) ====================
        st.markdown("## 🔥 Ordini Attivi (Da Eseguire)")
        
        ordini_attivi = df_ordini[df_ordini['STATO ESECUZIONE'] == 'Attivo'].copy()
        
        if ordini_attivi.empty:
            st.success("✅ Nessun ordine attivo al momento")
        else:
            st.info(f"📋 **{len(ordini_attivi)} ordini** in attesa di esecuzione")
            
            # Visualizza ordini attivi come card in evidenza
            for idx, ordine in ordini_attivi.iterrows():
                original_row_number = ordine['ROW_NUMBER']
                
                # Card con bordo colorato
                with st.container():
                    # Badge operazione
                    op_color = "🟢" if ordine.get('OPERAZIONE') == 'Buy' else "🔴"
                    
                    col_header, col_badge = st.columns([3, 1])
                    
                    with col_header:
                        strumento = ordine.get('STRUMENTO', 'N/A')
                        operazione = ordine.get('OPERAZIONE', 'N/A')
                        st.markdown(f"### {op_color} **{strumento}** - {operazione}")
                    
                    with col_badge:
                        st.warning("⏳ **ATTIVO**")
                    
                    # Dettagli
                    col_det1, col_det2, col_det3, col_det4 = st.columns(4)
                    
                    with col_det1:
                        if 'RESPONSABILE' in ordine:
                            st.markdown(f"**👤 Responsabile:** {ordine['RESPONSABILE']}")
                        if 'ESITO' in ordine and pd.notna(ordine['ESITO']):
                            st.markdown(f"**⭐ Esito:** {ordine['ESITO']}/5")
                    
                    with col_det2:
                        if 'QUANTITA' in ordine:
                            st.markdown(f"**📊 Quantità:** {ordine['QUANTITA']}")
                        if 'PMC' in ordine and 'VALUTA' in ordine:
                            pmc_val = ordine['PMC']
                            valuta = ordine['VALUTA']
                            st.markdown(f"**💵 PMC:** {pmc_val} {valuta}")
                    
                    with col_det3:
                        if 'SL' in ordine:
                            sl_val = ordine['SL'] if pd.notna(ordine['SL']) and ordine['SL'] != '' else 'N/A'
                            st.markdown(f"**🛑 SL:** {sl_val}")
                        if 'TP' in ordine:
                            tp_val = ordine['TP'] if pd.notna(ordine['TP']) and ordine['TP'] != '' else 'N/A'
                            st.markdown(f"**🎯 TP:** {tp_val}")
                    
                    with col_det4:
                        if 'DATA PROPOSTA' in ordine and pd.notna(ordine['DATA PROPOSTA']):
                            st.markdown(f"**📅 Proposta:** {ordine['DATA PROPOSTA'].strftime('%d/%m/%Y')}")
                        
                        # Calcola valore ordine
                        if 'QUANTITA' in ordine and 'PMC' in ordine:
                            qty = pd.to_numeric(ordine['QUANTITA'], errors='coerce')
                            pmc = pd.to_numeric(ordine['PMC'], errors='coerce')
                            if pd.notna(qty) and pd.notna(pmc):
                                valore = qty * pmc
                                st.markdown(f"**💰 Valore:** € {valore:,.2f}")
                    
                    # Azioni
                    col_az1, col_az2, col_az3 = st.columns([1, 1, 2])
                    
                    with col_az1:
                        if st.button("✅ Segna Eseguito", key=f"esegui_{original_row_number}", use_container_width=True, type="primary"):
                            data_esecuzione = datetime.now().strftime('%d/%m/%Y')
                            with st.spinner("⏳ Aggiornamento..."):
                                success, message = aggiorna_stato_ordine_via_webhook(
                                    original_row_number,
                                    'Eseguito',
                                    data_esecuzione,
                                    WEBHOOK_URL_ORDINI
                                )
                            if success:
                                st.success(f"✅ {message}")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
                    
                    with col_az2:
                        if st.button("❌ Cancella Ordine", key=f"cancella_{original_row_number}", use_container_width=True):
                            data_cancellazione = datetime.now().strftime('%d/%m/%Y')
                            with st.spinner("⏳ Cancellazione..."):
                                success, message = aggiorna_stato_ordine_via_webhook(
                                    original_row_number,
                                    'Cancellato',
                                    data_cancellazione,
                                    WEBHOOK_URL_ORDINI
                                )
                            if success:
                                st.success(f"✅ {message}")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
                    
                    st.markdown("---")
        
        # ==================== SEZIONE ORDINI ESEGUITI (TABELLA) ====================
        st.markdown("---")
        st.markdown("## ✅ Storico Ordini Eseguiti")
        
        ordini_eseguiti = df_ordini[df_ordini['STATO ESECUZIONE'] == 'Eseguito'].copy()
        
        if ordini_eseguiti.empty:
            st.info("Nessun ordine eseguito")
        else:
            st.success(f"📊 {len(ordini_eseguiti)} ordini completati")
            
            # Prepara dati per tabella
            df_display_eseguiti = ordini_eseguiti.copy()
            
            if 'DATA PROPOSTA' in df_display_eseguiti.columns:
                df_display_eseguiti['DATA PROPOSTA'] = df_display_eseguiti['DATA PROPOSTA'].apply(
                    lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else ''
                )
            
            if 'DATA ESECUZIONE' in df_display_eseguiti.columns:
                df_display_eseguiti['DATA ESECUZIONE'] = df_display_eseguiti['DATA ESECUZIONE'].apply(
                    lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else ''
                )
            
            # Seleziona colonne da mostrare
            colonne_tabella = [
                'DATA PROPOSTA', 'STRUMENTO', 'OPERAZIONE', 'RESPONSABILE',
                'QUANTITA', 'PMC', 'VALUTA', 'ESITO', 'DATA ESECUZIONE'
            ]
            colonne_disponibili = [col for col in colonne_tabella if col in df_display_eseguiti.columns]
            
            # Mostra tabella
            st.dataframe(
                df_display_eseguiti[colonne_disponibili],
                use_container_width=True,
                height=400,
                hide_index=True
            )
            
            # Export CSV
            csv_eseguiti = df_display_eseguiti[colonne_disponibili].to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Scarica Ordini Eseguiti (CSV)",
                data=csv_eseguiti,
                file_name=f"ordini_eseguiti_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=False
            )
        
        # ==================== SEZIONE ORDINI CANCELLATI (TABELLA) ====================
        st.markdown("---")
        st.markdown("## ❌ Ordini Cancellati")
        
        ordini_cancellati = df_ordini[df_ordini['STATO ESECUZIONE'] == 'Cancellato'].copy()
        
        if ordini_cancellati.empty:
            st.info("Nessun ordine cancellato")
        else:
            with st.expander(f"📋 Mostra {len(ordini_cancellati)} ordini cancellati"):
                # Prepara dati per tabella
                df_display_cancellati = ordini_cancellati.copy()
                
                if 'DATA PROPOSTA' in df_display_cancellati.columns:
                    df_display_cancellati['DATA PROPOSTA'] = df_display_cancellati['DATA PROPOSTA'].apply(
                        lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else ''
                    )
                
                if 'DATA ESECUZIONE' in df_display_cancellati.columns:
                    df_display_cancellati['DATA ESECUZIONE'] = df_display_cancellati['DATA ESECUZIONE'].apply(
                        lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else ''
                    )
                
                colonne_disponibili_canc = [col for col in colonne_tabella if col in df_display_cancellati.columns]
                
                st.dataframe(
                    df_display_cancellati[colonne_disponibili_canc],
                    use_container_width=True,
                    height=300,
                    hide_index=True
                )
                
                # Bottone per riattivare ordini cancellati
                st.markdown("**Riattiva ordini cancellati:**")
                for idx, ordine in ordini_cancellati.iterrows():
                    col_info, col_btn = st.columns([3, 1])
                    with col_info:
                        st.caption(f"{ordine.get('STRUMENTO', 'N/A')} - {ordine.get('OPERAZIONE', 'N/A')}")
                    with col_btn:
                        if st.button("🔄 Riattiva", key=f"riattiva_{ordine['ROW_NUMBER']}", use_container_width=True):
                            with st.spinner("⏳ Riattivazione..."):
                                success, message = aggiorna_stato_ordine_via_webhook(
                                    ordine['ROW_NUMBER'],
                                    'Attivo',
                                    '',
                                    WEBHOOK_URL_ORDINI
                                )
                            if success:
                                st.success(f"✅ {message}")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
    
    except Exception as e:
        st.error(f"❌ Errore nel caricamento ordini: {str(e)}")
        st.info("💡 Verifica che il foglio Ordini sia condiviso pubblicamente")


if __name__ == "__main__":
    ordini_app()
