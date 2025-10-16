import streamlit as st
import pandas as pd
from datetime import datetime


@st.cache_data(ttl=120)
def load_sheet_csv_proposte(spreadsheet_id, gid):
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


def proposte_app():
    """Applicazione Gestione Proposte"""
    
    st.title("📝 Gestione Proposte di Investimento")
    st.markdown("---")
    
    # ID del foglio Google Sheets
    spreadsheet_id = "1WEt_YQCASRr5EWFk77DbBI6DcOIw2ifRIMlzAaG58uY"
    gid_proposte = "836776830"  # ⚠️ SOSTITUISCI CON IL GID CORRETTO DEL FOGLIO "Proposte"
    
    # Opzioni sidebar
    st.sidebar.markdown("### ⚙️ Opzioni Proposte")
    
    # Bottone refresh
    if st.sidebar.button("🔄 Aggiorna Proposte", type="primary"):
        st.cache_data.clear()
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.caption("💡 I dati vengono aggiornati automaticamente ogni 2 minuti")
    
    try:
        with st.spinner("Caricamento proposte dal Google Sheet..."):
            df_proposte = load_sheet_csv_proposte(spreadsheet_id, gid_proposte)
        
        if df_proposte is None or df_proposte.empty:
            st.error("❌ Impossibile caricare il foglio 'Proposte'")
            st.info("💡 Verifica che il foglio sia pubblico: Condividi → Chiunque con il link → Visualizzatore")
            st.stop()
        
        # Definisci i nomi delle colonne attese
        expected_columns = [
            'Informazioni cronologiche',
            'Responsabile proposta',
            'Buy / Sell',
            'Quale strumento ?',
            'Quantità ?',
            'PMC ?',
            'SL ?',
            'TP ?',
            'Orizzonte temporale investimento',
            'Allegato',
            'Motivazione',
            'Link',
            'Immagine',
            'In che valuta è lo strumento ?',
            'ESITO',
            'GALLOZ',
            'STE',
            'GARGIU',
            'ALE',
            'GIACA'
        ]
        
        if len(df_proposte.columns) >= 20:
            df_proposte.columns = expected_columns
        else:
            st.warning(f"⚠️ Il foglio ha {len(df_proposte.columns)} colonne, ne servono 20")
        
        # ⭐ CONVERTI DATE CON GESTIONE PUNTI NELL'ORARIO ⭐
        # Sostituisci punti nell'orario (15.19.26 → 15:19:26)
        df_proposte['Informazioni cronologiche'] = df_proposte['Informazioni cronologiche'].astype(str).str.replace(
            r'(\d{2})\.(\d{2})\.(\d{2})', 
            r'\1:\2:\3', 
            regex=True
        )
        
        # Converti in datetime con formato italiano
        df_proposte['Informazioni cronologiche'] = pd.to_datetime(
            df_proposte['Informazioni cronologiche'],
            format='%d/%m/%Y %H:%M:%S',
            errors='coerce',
            dayfirst=True
        )
        
        # Converti Orizzonte temporale investimento
        df_proposte['Orizzonte temporale investimento'] = pd.to_datetime(
            df_proposte['Orizzonte temporale investimento'],
            format='%d/%m/%Y',
            errors='coerce',
            dayfirst=True
        )
        
        # Converti ESITO in numerico
        df_proposte['ESITO'] = pd.to_numeric(df_proposte['ESITO'], errors='coerce')
        
        # Rimuovi righe completamente vuote
        df_proposte = df_proposte.dropna(how='all')
        
        # Ordina per data decrescente (più recenti prima)
        df_proposte = df_proposte.sort_values('Informazioni cronologiche', ascending=False).reset_index(drop=True)
        
        st.success(f"✅ {len(df_proposte)} proposte caricate con successo!")

        
        # ==================== FILTRI SIDEBAR ====================
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🔍 Filtri")
        
        # Filtro per responsabile
        responsabili_unici = []
        for resp in df_proposte['Responsabile proposta'].dropna().unique():
            if isinstance(resp, str):
                # Gestisci scelte multiple separate da virgola o spazio
                responsabili_unici.extend([r.strip() for r in resp.replace(',', ' ').split()])
        responsabili_unici = sorted(list(set(responsabili_unici)))
        
        responsabile_filter = st.sidebar.multiselect(
            "Responsabile",
            options=responsabili_unici,
            default=[]
        )
        
        # Filtro Buy/Sell
        buysell_options = df_proposte['Buy / Sell'].dropna().unique().tolist()
        buysell_filter = st.sidebar.multiselect(
            "Operazione",
            options=buysell_options,
            default=buysell_options
        )
        
        # Filtro Valuta
        valute_options = sorted(df_proposte['In che valuta è lo strumento ?'].dropna().unique().tolist())
        valuta_filter = st.sidebar.multiselect(
            "Valuta",
            options=valute_options,
            default=[]
        )
        
        # Filtro ESITO
        esito_filter = st.sidebar.slider(
            "ESITO minimo",
            min_value=1.0,
            max_value=5.0,
            value=1.0,
            step=0.5,
            help="Filtra proposte con ESITO >= valore selezionato"
        )
        
        # Applica filtri
        df_filtered = df_proposte.copy()
        
        if responsabile_filter:
            df_filtered = df_filtered[
                df_filtered['Responsabile proposta'].apply(
                    lambda x: any(r in str(x) for r in responsabile_filter) if pd.notna(x) else False
                )
            ]
        
        if buysell_filter:
            df_filtered = df_filtered[df_filtered['Buy / Sell'].isin(buysell_filter)]
        
        if valuta_filter:
            df_filtered = df_filtered[df_filtered['In che valuta è lo strumento ?'].isin(valuta_filter)]
        
        # ⭐ FILTRO ESITO: INCLUDI ANCHE PROPOSTE NON VOTATE (NaN) ⭐
        df_filtered = df_filtered[
            (df_filtered['ESITO'] >= esito_filter) | (df_filtered['ESITO'].isna())
        ]
        
        # Riordina dopo i filtri
        df_filtered = df_filtered.sort_values('Informazioni cronologiche', ascending=False).reset_index(drop=True)

        # ==================== TABELLA PROPOSTE CON FORMATTAZIONE ====================
        st.markdown("---")
        st.subheader("📋 DETTAGLIO PROPOSTE")
        st.caption("🔽 Ordinate dalla più recente")
        
        # Prepara dataframe per visualizzazione
        df_display = df_filtered.copy()
        
        # Formatta le date (solo data, senza orario)
        df_display['Informazioni cronologiche'] = df_display['Informazioni cronologiche'].apply(
            lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else ''
        )
        df_display['Orizzonte temporale investimento'] = df_display['Orizzonte temporale investimento'].apply(
            lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else ''
        )
        
        # Funzione per colorare ESITO
        def color_esito(val):
            if pd.isna(val):
                return 'background-color: #555555; color: white; font-style: italic'  # Grigio per non votate
            if val >= 3:
                return 'background-color: #2ecc71; color: white; font-weight: bold'   # Verde approvate
            else:
                return 'background-color: #e74c3c; color: white; font-weight: bold'   # Rosso respinte

        # Applica stile condizionale
        styled_df = df_display.style.map(color_esito, subset=['ESITO'])
        
        # Mostra tabella
        st.dataframe(
            styled_df,
            use_container_width=True,
            height=600,
            hide_index=True
        )


        
        # ==================== DETTAGLIO SINGOLA PROPOSTA ====================
        st.markdown("---")
        st.subheader("🔍 Dettaglio Proposta")
        
        if len(df_filtered) > 0:
            # Selettore proposta
            strumenti_list = df_filtered['Quale strumento ?'].tolist()
            # Formatta le date per il selettore
            date_list = df_filtered['Informazioni cronologiche'].apply(
                lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else 'Data non disponibile'
            ).tolist()
            
            options = [f"{strumento} - {data}" for strumento, data in zip(strumenti_list, date_list)]

            selected_idx = st.selectbox(
                "Seleziona una proposta",
                range(len(options)),
                format_func=lambda x: options[x]
            )
            
            proposta = df_filtered.iloc[selected_idx]
            
            # Box colorato in base all'ESITO
            esito_val = proposta['ESITO']
            if pd.isna(esito_val):
                st.warning("⚠️ PROPOSTA NON ANCORA VOTATA")
            elif esito_val >= 3:
                st.success(f"✅ ESITO: {esito_val} - PROPOSTA APPROVATA")
            else:
                st.error(f"❌ ESITO: {esito_val} - PROPOSTA RESPINTA")

            # Mostra dettagli in colonne
            col_det1, col_det2, col_det3 = st.columns(3)
            
            with col_det1:
                st.markdown("##### 📌 Informazioni Base")
                st.write(f"**Strumento:** {proposta['Quale strumento ?']}")
                st.write(f"**Operazione:** {proposta['Buy / Sell']}")
                st.write(f"**Responsabile:** {proposta['Responsabile proposta']}")
                st.write(f"**Data proposta:** {proposta['Informazioni cronologiche']}")
            
            with col_det2:
                st.markdown("##### 💰 Dati Finanziari")
                st.write(f"**Quantità:** {proposta['Quantità ?']}")
                st.write(f"**PMC:** {proposta['PMC ?']}")
                st.write(f"**SL:** {proposta['SL ?']}")
                st.write(f"**TP:** {proposta['TP ?']}")
                st.write(f"**Valuta:** {proposta['In che valuta è lo strumento ?']}")
            
            with col_det3:
                st.markdown("##### ✅ Votazione")
                
                if pd.notna(proposta['ESITO']):
                    st.write(f"**ESITO:** {proposta['ESITO']}")
                else:
                    st.write(f"**ESITO:** Non disponibile")
                
                # Mostra votazioni con icone
                votazioni = {
                    'GALLOZ': proposta['GALLOZ'],
                    'STE': proposta['STE'],
                    'GARGIU': proposta['GARGIU'],
                    'ALE': proposta['ALE'],
                    'GIACA': proposta['GIACA']
                }
                
                for nome, voto in votazioni.items():
                    voto_str = str(voto).lower().strip()
                    if voto_str == 'x':
                        st.write(f"✅ **{nome}**: Favorevole")
                    elif voto_str == 'o':
                        st.write(f"❌ **{nome}**: Contrario")
                    else:
                        st.write(f"⚪ **{nome}**: Non ha votato")

                
                for nome, voto in votazioni.items():
                    if str(voto).lower() == 'x':
                        st.write(f"✅ **{nome}**: Favorevole")
                    elif str(voto).lower() == 'o':
                        st.write(f"❌ **{nome}**: Contrario")
                    else:
                        st.write(f"⚪ **{nome}**: Non votato")
            
            # Motivazione in un box separato
            st.markdown("---")
            st.markdown("##### 📝 Motivazione")
            st.info(proposta['Motivazione'] if pd.notna(proposta['Motivazione']) else "Nessuna motivazione fornita")
            
            # Orizzonte temporale
            st.markdown("##### 📅 Orizzonte Temporale")
            st.write(proposta['Orizzonte temporale investimento'] if pd.notna(proposta['Orizzonte temporale investimento']) else "Non specificato")
            
            # Link e immagini
            col_link1, col_link2 = st.columns(2)
            
            with col_link1:
                if pd.notna(proposta['Link']) and proposta['Link']:
                    st.markdown(f"##### 🔗 [Apri Link Allegato]({proposta['Link']})")
                else:
                    st.caption("Nessun link allegato")
            
            with col_link2:
                if pd.notna(proposta['Immagine']) and proposta['Immagine']:
                    st.markdown(f"##### 🖼️ [Visualizza Immagine]({proposta['Immagine']})")
                else:
                    st.caption("Nessuna immagine allegata")
        else:
            st.info("ℹ️ Nessuna proposta disponibile con i filtri selezionati")
        
        # ==================== EXPORT CSV ====================
        st.markdown("---")
        
        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Scarica Proposte Filtrate (CSV)",
            data=csv,
            file_name=f"proposte_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
    except Exception as e:
        st.error(f"❌ Errore nel caricamento delle proposte: {str(e)}")
        st.info("💡 Verifica che il foglio Google Sheets sia pubblicamente accessibile.")
        
        with st.expander("🔍 Dettagli errore"):
            st.code(str(e))
