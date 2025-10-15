import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


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


def transaction_tracker_app():
    """Applicazione Transaction Tracker"""
    
    st.title("💳 Transaction Tracker")
    st.markdown("---")
    
    # ID del foglio Google Sheets
    spreadsheet_id = "1mD9jxDJv26aZwCdIbvQVjlJGBhRwKWwQnPpPPq0ON5Y"
    gid_transactions = 1594640549
    
    # Opzioni sidebar
    st.sidebar.markdown("### ⚙️ Opzioni Transazioni")
    
    # Bottone refresh
    if st.sidebar.button("🔄 Aggiorna Transazioni", type="primary"):
        st.cache_data.clear()
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.caption("💡 I dati vengono aggiornati automaticamente ogni 2 minuti")
    
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
