import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import json

# Configurazione pagina
st.set_page_config(
    page_title="Gestione Ordini",
    page_icon="📋",
    layout="wide"
)

# Funzione per connettersi a Google Sheets
@st.cache_resource
def get_google_sheets_client():
    """Inizializza il client Google Sheets con le credenziali"""
    try:
        # Carica le credenziali da Streamlit secrets
        creds_dict = st.secrets["gcp_service_account"]
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = Credentials.from_service_account_info(
            creds_dict,
            scopes=scopes
        )
        
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"Errore nella connessione a Google Sheets: {str(e)}")
        return None

def leggi_proposte_approvate(gc):
    """Legge le proposte dal foglio Google Sheets e filtra quelle approvate (esito >= 3)"""
    try:
        # Apri il foglio "Proposte"
        spreadsheet = gc.open_by_key(st.secrets["google_sheets"]["proposte_sheet_id"])
        worksheet = spreadsheet.worksheet("Proposte")
        
        # Leggi tutti i dati
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Filtra le proposte approvate (esito >= 3)
        if 'Esito' in df.columns:
            df_approvate = df[df['Esito'] >= 3].copy()
            
            # Aggiungi colonna Stato Esecuzione se non esiste
            if 'Stato Esecuzione' not in df_approvate.columns:
                df_approvate['Stato Esecuzione'] = 'In Attesa'
            
            # Aggiungi colonna Data Esecuzione se non esiste
            if 'Data Esecuzione' not in df_approvate.columns:
                df_approvate['Data Esecuzione'] = ''
            
            return df_approvate, worksheet
        else:
            st.error("La colonna 'Esito' non è presente nel foglio Proposte")
            return pd.DataFrame(), None
            
    except Exception as e:
        st.error(f"Errore nella lettura delle proposte: {str(e)}")
        return pd.DataFrame(), None

def aggiorna_stato_ordine(worksheet, row_index, nuovo_stato):
    """Aggiorna lo stato di esecuzione di un ordine nel foglio Google Sheets"""
    try:
        # Trova le colonne di Stato Esecuzione e Data Esecuzione
        header = worksheet.row_values(1)
        
        # Trova l'indice della colonna Stato Esecuzione
        if 'Stato Esecuzione' in header:
            col_stato = header.index('Stato Esecuzione') + 1
        else:
            # Se non esiste, aggiungila
            col_stato = len(header) + 1
            worksheet.update_cell(1, col_stato, 'Stato Esecuzione')
        
        # Trova l'indice della colonna Data Esecuzione
        if 'Data Esecuzione' in header:
            col_data = header.index('Data Esecuzione') + 1
        else:
            # Se non esiste, aggiungila
            col_data = len(header) + 2
            worksheet.update_cell(1, col_data, 'Data Esecuzione')
        
        # Aggiorna lo stato
        worksheet.update_cell(row_index + 2, col_stato, nuovo_stato)  # +2 perché row_index parte da 0 e la riga 1 è l'header
        
        # Se lo stato è "Eseguito", aggiungi anche la data
        if nuovo_stato == "Eseguito":
            data_esecuzione = datetime.now().strftime("%Y-%m-%d")
            worksheet.update_cell(row_index + 2, col_data, data_esecuzione)
        else:
            worksheet.update_cell(row_index + 2, col_data, "")
        
        return True
    except Exception as e:
        st.error(f"Errore nell'aggiornamento dello stato: {str(e)}")
        return False

# Main
def main():
    st.title("📋 Gestione Ordini da Proposte Approvate")
    st.markdown("---")
    
    # Inizializza il client Google Sheets
    gc = get_google_sheets_client()
    
    if gc is None:
        st.error("Impossibile connettersi a Google Sheets. Verifica le credenziali.")
        return
    
    # Leggi le proposte approvate
    df_proposte, worksheet = leggi_proposte_approvate(gc)
    
    if df_proposte.empty:
        st.warning("Nessuna proposta approvata trovata (esito >= 3)")
        return
    
    # Filtri
    st.sidebar.header("🔍 Filtri")
    
    # Contatori per i badge
    totali = len(df_proposte)
    in_attesa = len(df_proposte[df_proposte['Stato Esecuzione'] == 'In Attesa'])
    eseguiti = len(df_proposte[df_proposte['Stato Esecuzione'] == 'Eseguito'])
    
    filtro_stato = st.sidebar.radio(
        "Filtra per stato:",
        options=["Tutti", "In Attesa", "Eseguito"],
        format_func=lambda x: f"{x} ({totali if x == 'Tutti' else in_attesa if x == 'In Attesa' else eseguiti})"
    )
    
    # Applica il filtro
    if filtro_stato != "Tutti":
        df_filtrato = df_proposte[df_proposte['Stato Esecuzione'] == filtro_stato].copy()
    else:
        df_filtrato = df_proposte.copy()
    
    # Mostra statistiche
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📊 Totale Proposte Approvate", totali)
    
    with col2:
        st.metric("⏳ In Attesa", in_attesa)
    
    with col3:
        st.metric("✅ Eseguiti", eseguiti)
    
    st.markdown("---")
    
    # Mostra le proposte
    if df_filtrato.empty:
        st.info(f"Nessuna proposta con stato '{filtro_stato}'")
    else:
        st.subheader(f"Proposte {filtro_stato}")
        
        # Visualizza ogni proposta come card
        for idx, row in df_filtrato.iterrows():
            with st.container():
                # Trova l'indice originale nel dataframe completo
                original_idx = df_proposte.index.get_loc(idx)
                
                col_info, col_azioni = st.columns([3, 1])
                
                with col_info:
                    # Badge per l'esito
                    esito_color = "🟢" if row['Esito'] >= 4 else "🟡"
                    st.markdown(f"### {esito_color} {row.get('Descrizione', 'N/A')}")
                    
                    col_det1, col_det2, col_det3 = st.columns(3)
                    
                    with col_det1:
                        st.markdown(f"**Esito:** {row['Esito']}/5")
                    
                    with col_det2:
                        data_creazione = row.get('Data Creazione', 'N/A')
                        st.markdown(f"**Data Creazione:** {data_creazione}")
                    
                    with col_det3:
                        if row.get('Data Esecuzione'):
                            st.markdown(f"**Data Esecuzione:** {row['Data Esecuzione']}")
                
                with col_azioni:
                    stato_attuale = row['Stato Esecuzione']
                    
                    # Pulsanti per cambiare stato
                    if stato_attuale == 'In Attesa':
                        if st.button("✅ Segna come Eseguito", key=f"esegui_{idx}"):
                            if aggiorna_stato_ordine(worksheet, original_idx, "Eseguito"):
                                st.success("Ordine segnato come eseguito!")
                                st.rerun()
                    else:
                        if st.button("⏳ Riporta in Attesa", key=f"attesa_{idx}"):
                            if aggiorna_stato_ordine(worksheet, original_idx, "In Attesa"):
                                st.success("Ordine riportato in attesa!")
                                st.rerun()
                    
                    # Badge stato
                    if stato_attuale == 'Eseguito':
                        st.success("✅ Eseguito")
                    else:
                        st.warning("⏳ In Attesa")
                
                st.markdown("---")
        
        # Tabella riassuntiva
        with st.expander("📊 Visualizza Tabella Completa"):
            # Seleziona solo le colonne rilevanti
            colonne_visualizzate = ['Descrizione', 'Esito', 'Data Creazione', 'Stato Esecuzione', 'Data Esecuzione']
            colonne_disponibili = [col for col in colonne_visualizzate if col in df_filtrato.columns]
            
            st.dataframe(
                df_filtrato[colonne_disponibili],
                use_container_width=True,
                hide_index=True
            )

if __name__ == "__main__":
    main()
