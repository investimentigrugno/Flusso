import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import requests


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


def append_proposta_via_webhook(proposta_data, webhook_url):
    """
    Invia proposta al Google Apps Script webhook
    
    Args:
        proposta_ Dizionario con i dati della proposta
        webhook_url: URL del webhook Google Apps Script
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Prepara i dati per il webhook
        payload = {
            "data_cronologica": proposta_data['DATA'],
            "responsabile": proposta_data['RESPONSABILE'],
            "buy_sell": proposta_data['OPERAZIONE'],
            "strumento": proposta_data['STRUMENTO'],
            "quantita": proposta_data['QUANTITA'],
            "pmc": proposta_data['PMC'],
            "sl": proposta_data['SL'],
            "tp": proposta_data['TP'],
            "orizzonte": proposta_data['ORIZZONTE TEMPORALE'],
            "ALLEGATO": proposta_data['ALLEGATO'],
            "MOTIVAZIONE": proposta_data['MOTIVAZIONE'],
            "LINK": proposta_data['LINK'],
            "IMMAGINE": proposta_data['IMMAGINE'],
            "valuta": proposta_data['VALUTA']
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


def proposte_app():
    """Applicazione Gestione Proposte"""
    
    st.title("📝 Gestione Proposte di Investimento")
    st.markdown("---")
    
    # ID del foglio Google Sheets
    spreadsheet_id = "1WEt_YQCASRr5EWFk77DbBI6DcOIw2ifRIMlzAaG58uY"
    gid_proposte = "836776830"
    
    # ==================== CONFIGURAZIONE WEBHOOK ====================
    WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbwPSIjUt9gAYh0EY1vuoqEgyqQTSxxUrQgjGZqGrOFx4BWDeWbZCwcThGlivJsHznkD/exec"
    
    # Opzioni sidebar
    st.sidebar.markdown("### ⚙️ Opzioni Proposte")
    
    # Bottone refresh
    if st.sidebar.button("🔄 Aggiorna Proposte", type="primary"):
        st.cache_data.clear()
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.caption("💡 I dati vengono aggiornati automaticamente ogni 2 minuti")
    
    # ==================== TABS ====================
    tab1, tab2 = st.tabs(["📊 Visualizza Proposte", "➕ Aggiungi Proposta"])
    
    # ==================== TAB 1: VISUALIZZA PROPOSTE ====================
    with tab1:
        try:
            with st.spinner("Caricamento proposte dal Google Sheet..."):
                df_proposte = load_sheet_csv_proposte(spreadsheet_id, gid_proposte)
            
            if df_proposte is None or df_proposte.empty:
                st.error("❌ Impossibile caricare il foglio 'Proposte'")
                st.info("💡 Verifica che il foglio sia pubblico: Condividi → Chiunque con il LINK → Visualizzatore")
                st.stop()
            
            # Definisci i nomi delle colonne attese
            expected_columns = [
                'DATA',
                'RESPONSABILE',
                'OPERAZIONE',
                'STRUMENTO',
                'QUANTITA',
                'PMC',
                'SL',
                'TP',
                'ORIZZONTE TEMPORALE',
                'ALLEGATO',
                'MOTIVAZIONE',
                'LINK',
                'IMMAGINE',
                'VALUTA',
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
            
            df_proposte['ORIZZONTE TEMPORALE'] = pd.to_datetime(
                df_proposte['ORIZZONTE TEMPORALE'],
                format='%d/%m/%Y',
                errors='coerce',
                dayfirst=True
            )
            
                        # Converti ESITO in numerico INTERO
            df_proposte['ESITO'] = pd.to_numeric(df_proposte['ESITO'], errors='coerce').astype('Int64')
            
            # Rimuovi righe vuote
            colonne_chiave = ['STRUMENTO', 'OPERAZIONE', 'RESPONSABILE']
            mask_valide = df_proposte[colonne_chiave].notna().any(axis=1)
            df_proposte = df_proposte[mask_valide]
            
            # Ordina per data decrescente
            df_proposte = df_proposte.sort_values(
                'DATA',
                ascending=False,
                na_position='last'
            ).reset_index(drop=True)
            
            st.success(f"✅ {len(df_proposte)} proposte caricate con successo!")
            
            # ==================== FILTRI SIDEBAR ====================
            st.sidebar.markdown("---")
            st.sidebar.markdown("### 🔍 Filtri")
            
            # Filtro per responsabile
            responsabili_unici = []
            for resp in df_proposte['RESPONSABILE'].dropna().unique():
                if isinstance(resp, str):
                    responsabili_unici.extend([r.strip() for r in resp.replace(',', ' ').split()])
            responsabili_unici = sorted(list(set(responsabili_unici)))
            
            responsabile_filter = st.sidebar.multiselect(
                "Responsabile",
                options=responsabili_unici,
                default=[]
            )
            
            # Filtro Buy/Sell
            buysell_options = df_proposte['OPERAZIONE'].dropna().unique().tolist()
            buysell_filter = st.sidebar.multiselect(
                "Operazione",
                options=buysell_options,
                default=buysell_options
            )
            
            # ⭐ Filtro ESITO (intero 0-5) ⭐
            esito_options = st.sidebar.radio(
                "Stato Votazione",
                options=["Tutte", "Approvate (≥3)", "Respinte (<3)", "Non votate"],
                index=0,
                help="ESITO = somma voti (x=1, o=0). Range: 0-5"
            )
            
            # Applica filtri
            df_filtered = df_proposte.copy()
            
            if responsabile_filter:
                df_filtered = df_filtered[
                    df_filtered['RESPONSABILE'].apply(
                        lambda x: any(r in str(x) for r in responsabile_filter) if pd.notna(x) else False
                    )
                ]
            
            if buysell_filter:
                df_filtered = df_filtered[df_filtered['OPERAZIONE'].isin(buysell_filter)]
            
            # ⭐ Applica filtro ESITO (confronto con interi) ⭐
            if esito_options == "Approvate (≥3)":
                df_filtered = df_filtered[df_filtered['ESITO'] >= 3]
            elif esito_options == "Respinte (<3)":
                df_filtered = df_filtered[df_filtered['ESITO'] < 3]
            elif esito_options == "Non votate":
                df_filtered = df_filtered[df_filtered['ESITO'].isna()]
            # Se "Tutte" non applicare filtro
            
            # Riordina dopo i filtri
            df_filtered = df_filtered.sort_values('DATA', ascending=False).reset_index(drop=True)

                        # ==================== GRAFICO A BARRE ====================
            st.markdown("---")
            st.subheader("📊 Proposte per Responsabile")
            
            # Conta tutte le proposte per responsabile (singoli e squadra)
            resp_counts = {}
            for resp in df_filtered['RESPONSABILE'].dropna():
                if isinstance(resp, str):
                    nomi = [r.strip() for r in resp.replace(',', ' ').split()]
                    for nome in nomi:
                        resp_counts[nome] = resp_counts.get(nome, 0) + 1
            
            if resp_counts:
                df_resp = pd.DataFrame(list(resp_counts.items()), columns=['Responsabile', 'Proposte'])
                df_resp = df_resp.sort_values('Proposte', ascending=True)
                
                fig_resp = px.bar(
                    df_resp,
                    x='Proposte',
                    y='Responsabile',
                    orientation='h',
                    color='Proposte',
                    color_continuous_scale='Blues',
                    text='Proposte'
                )
                
                fig_resp.update_traces(
                    texttemplate='%{text}',
                    textposition='outside'
                )
                
                fig_resp.update_layout(
                    plot_bgcolor='#0e1117',
                    paper_bgcolor='#0e1117',
                    font={'color': 'white'},
                    xaxis={
                        'title': dict(text='Numero Proposte', font=dict(color='white')), 
                        'color': 'white', 
                        'gridcolor': '#333333'
                    },
                    yaxis={
                        'title': dict(text='', font=dict(color='white')), 
                        'color': 'white'
                    },
                    height=400,
                    showlegend=False
                )
                
                st.plotly_chart(fig_resp, use_container_width=True)
            else:
                st.info("Nessuna proposta disponibile")

            # ==================== TABELLA PROPOSTE ====================
            st.markdown("---")
            st.subheader("📋 DETTAGLIO PROPOSTE")
            st.caption("🔽 Ordinate dalla più recente")
            
            df_display = df_filtered.copy()
            
            df_display['DATA'] = df_display['DATA'].apply(
                lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else ''
            )
            
            df_display['ORIZZONTE TEMPORALE'] = df_display['ORIZZONTE TEMPORALE'].apply(
                lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else ''
            )
            
            def color_esito(val):
                if pd.isna(val):
                    return 'background-color: #555555; color: white; font-style: italic'
                if val >= 3:
                    return 'background-color: #2ecc71; color: white; font-weight: bold'
                else:
                    return 'background-color: #e74c3c; color: white; font-weight: bold'
            
            styled_df = df_display.style.map(color_esito, subset=['ESITO'])
            
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
                strumenti_list = df_filtered['STRUMENTO'].tolist()
                date_list = df_filtered['DATA'].apply(
                    lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else 'Data non disponibile'
                ).tolist()
                
                options = [f"{strumento} - {data}" for strumento, data in zip(strumenti_list, date_list)]
                
                selected_idx = st.selectbox(
                    "Seleziona una proposta",
                    range(len(options)),
                    format_func=lambda x: options[x]
                )
                
                proposta = df_filtered.iloc[selected_idx]
                
                esito_val = proposta['ESITO']
                if pd.isna(esito_val):
                    st.warning("⚠️ PROPOSTA NON ANCORA VOTATA")
                elif esito_val >= 3:
                    st.success(f"✅ ESITO: {esito_val} - PROPOSTA APPROVATA")
                else:
                    st.error(f"❌ ESITO: {esito_val} - PROPOSTA RESPINTA")
                
                col_det1, col_det2, col_det3 = st.columns(3)
                
                with col_det1:
                    st.markdown("##### 📌 Informazioni Base")
                    st.write(f"**Strumento:** {proposta['STRUMENTO']}")
                    st.write(f"**Operazione:** {proposta['OPERAZIONE']}")
                    st.write(f"**Responsabile:** {proposta['RESPONSABILE']}")
                    
                    data_proposta = proposta['DATA']
                    if pd.notna(data_proposta):
                        st.write(f"**Data proposta:** {data_proposta.strftime('%d/%m/%Y')}")
                    else:
                        st.write(f"**Data proposta:** Non disponibile")
                
                with col_det2:
                    st.markdown("##### 💰 Dati Finanziari")
                    st.write(f"**Quantità:** {proposta['QUANTITA']}")
                    st.write(f"**PMC:** {proposta['PMC']}")
                    st.write(f"**SL:** {proposta['SL']}")
                    st.write(f"**TP:** {proposta['TP']}")
                    st.write(f"**Valuta:** {proposta['VALUTA']}")
                
                with col_det3:
                    st.markdown("##### ✅ Votazione")
                    
                    if pd.notna(proposta['ESITO']):
                        st.write(f"**ESITO:** {proposta['ESITO']}")
                    else:
                        st.write(f"**ESITO:** Non disponibile")
                    
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
                
                st.markdown("---")
                st.markdown("##### 📝 MOTIVAZIONE")
                st.info(proposta['MOTIVAZIONE'] if pd.notna(proposta['MOTIVAZIONE']) else "Nessuna MOTIVAZIONE fornita")
                
                st.markdown("##### 📅 Orizzonte Temporale")
                orizzonte = proposta['ORIZZONTE TEMPORALE']
                if pd.notna(orizzonte):
                    st.write(orizzonte.strftime('%d/%m/%Y'))
                else:
                    st.write("Non specificato")
                
                col_link1, col_link2 = st.columns(2)
                
                with col_link1:
                    if pd.notna(proposta['LINK']) and proposta['LINK']:
                        st.markdown(f"##### 🔗 [Apri LINK ALLEGATO]({proposta['LINK']})")
                    else:
                        st.caption("Nessun LINK ALLEGATO")
                
                with col_link2:
                    if pd.notna(proposta['IMMAGINE']) and proposta['IMMAGINE']:
                        st.markdown(f"##### 🖼️ [Visualizza IMMAGINE]({proposta['IMMAGINE']})")
                    else:
                        st.caption("Nessuna IMMAGINE allegata")
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
    
    # ==================== TAB 2: AGGIUNGI PROPOSTA ====================
    with tab2:
        st.subheader("➕ Aggiungi Nuova Proposta")
        st.markdown("---")
        
        # Verifica configurazione webhook
        if WEBHOOK_URL == "https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec":
            st.error("⚠️ URL del webhook non configurato!")
            st.info("Configura l'URL del webhook per Google Apps Script nelle secrets o nel codice.")
            st.stop()
        
        with st.form("new_proposta_form", clear_on_submit=True):
            st.markdown("### 📝 Dettagli Proposta")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Responsabili
                responsabili = st.multiselect(
                    "Responsabile/i Proposta *",
                    options=["GALLOZ", "STE", "GARGIU", "ALE", "GIACA"],
                    help="Seleziona uno o più responsabili"
                )
                
                # Buy/Sell
                buy_sell = st.selectbox(
                    "Operazione *",
                    options=["Buy", "Sell"],
                    help="Tipo di operazione"
                )
                
                # Strumento
                strumento = st.text_input(
                    "Strumento *",
                    placeholder="Es: AAPL, BTC-USD, TSLA",
                    help="Ticker o nome dello strumento"
                )
                
                # Quantità
                quantita = st.number_input(
                    "Quantità *",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.4f"
                )
                
                # PMC
                pmc = st.number_input(
                    "PMC (Prezzo Medio) *",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.4f"
                )
            
            with col2:
                # SL
                sl = st.number_input(
                    "Stop Loss",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.4f"
                )
                
                # TP
                tp = st.number_input(
                    "Take Profit",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.4f"
                )
                
                # Valuta
                valuta = st.selectbox(
                    "Valuta *",
                    options=["EUR", "USD", "GBP", "JPY", "AUD", "CAD", "NZD", "CNH", "SEK", "CHF"]
                )
                
                # Orizzonte temporale
                orizzonte = st.date_input(
                    "Orizzonte Temporale",
                    value=None,
                    help="Data obiettivo investimento"
                )
                
                # ALLEGATO
                allegato_tipo = st.selectbox(
                    "Tipo ALLEGATO",
                    options=["", "LINK", "IMMAGINE"]
                )
            
            # MOTIVAZIONE
            MOTIVAZIONE = st.text_area(
                "MOTIVAZIONE *",
                placeholder="Descrivi la MOTIVAZIONE della proposta (30-40 parole)",
                help="Spiega il razionale della proposta",
                height=100
            )
            
            # LINK/IMMAGINE
            col_all1, col_all2 = st.columns(2)
            
            with col_all1:
                LINK = st.text_input(
                    "LINK (URL)",
                    placeholder="https://...",
                    help="LINK a documento o analisi"
                )
            
            with col_all2:
                IMMAGINE = st.text_input(
                    "IMMAGINE (URL)",
                    placeholder="https://...",
                    help="LINK a IMMAGINE su Google Drive"
                )
            
            st.markdown("---")
            
            col_btn1, col_btn2 = st.columns([3, 1])
            
            with col_btn1:
                submitted = st.form_submit_button(
                    "💾 Salva Proposta",
                    type="primary",
                    use_container_width=True
                )
            
            with col_btn2:
                reset = st.form_submit_button(
                    "🔄 Reset",
                    use_container_width=True
                )
        
        if submitted:
            # Validazione
            errors = []
            
            if not responsabili:
                errors.append("⚠️ Seleziona almeno un responsabile")
            
            if not strumento:
                errors.append("⚠️ Il campo 'Strumento' è obbligatorio")
            
            if quantita <= 0:
                errors.append("⚠️ La 'Quantità' deve essere maggiore di 0")
            
            if pmc <= 0:
                errors.append("⚠️ Il 'PMC' deve essere maggiore di 0")
            
            if not MOTIVAZIONE:
                errors.append("⚠️ La 'MOTIVAZIONE' è obbligatoria")
            
            if errors:
                for error in errors:
                    st.error(error)
            else:
                # Crea nuova proposta
                now = datetime.now()
                
                def format_numero_italiano(numero, decimali=4):
                    formato = f"{{:.{decimali}f}}"
                    return formato.format(numero).replace('.', ',')
                
                new_proposta = {
                    'DATA': now.strftime('%d/%m/%Y %H.%M.%S'),
                    'RESPONSABILE': ', '.join(responsabili),
                    'OPERAZIONE': buy_sell,
                    'STRUMENTO': strumento,
                    'QUANTITA': format_numero_italiano(quantita, 4),
                    'PMC': format_numero_italiano(pmc, 4),
                    'SL': format_numero_italiano(sl, 4) if sl > 0 else '',
                    'TP': format_numero_italiano(tp, 4) if tp > 0 else '',
                    'ORIZZONTE TEMPORALE': orizzonte.strftime('%d/%m/%Y') if orizzonte else '',
                    'ALLEGATO': allegato_tipo,
                    'MOTIVAZIONE': MOTIVAZIONE,
                    'LINK': LINK,
                    'IMMAGINE': IMMAGINE,
                    'VALUTA': valuta
                }
                
                # Invia al webhook
                with st.spinner("💾 Salvataggio proposta in corso..."):
                    success, message = append_proposta_via_webhook(new_proposta, WEBHOOK_URL)
                
                if success:
                    st.success(f"✅ {message}")
                    st.balloons()
                    
                    st.markdown("### 👀 Proposta Salvata")
                    df_preview = pd.DataFrame([new_proposta])
                    st.dataframe(df_preview, use_container_width=True, hide_index=True)
                    
                    st.cache_data.clear()
                    
                    st.info("🔄 Torna al tab 'Visualizza Proposte' e clicca 'Aggiorna' per vedere la nuova proposta.")
                else:
                    st.error(f"❌ {message}")
                    st.warning("Verifica la configurazione del webhook.")
                    
                    df_preview = pd.DataFrame([new_proposta])
                    csv_new = df_preview.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Scarica Proposta (CSV Backup)",
                        data=csv_new,
                        file_name=f"proposta_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
        
        with st.expander("💡 Suggerimenti"):
            st.markdown("""
            - **Responsabile**: Puoi selezionare più persone per proposte di squadra
            - **Strumento**: Inserisci il ticker ufficiale
            - **PMC**: Prezzo medio di carico target
            - **SL/TP**: Stop Loss e Take Profit (opzionali)
            - **MOTIVAZIONE**: Spiega brevemente il razionale della proposta
            - **ALLEGATO**: Aggiungi LINK o immagini di supporto
            """)
