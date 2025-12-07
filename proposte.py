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

def get_exchange_rate(from_currency, to_currency='EUR'):
    """Ottiene il tasso di cambio da Frankfurter API"""
    if from_currency == to_currency:
        return 1.0
    try:
        url = f'https://api.frankfurter.app/latest?from={from_currency}&to={to_currency}'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data['rates'].get(to_currency, 1.0)
        return 1.0
    except Exception as e:
        st.sidebar.warning(f"Errore tasso cambio {from_currency}: {str(e)}")
        return 1.0


def append_proposta_via_webhook(proposta_data, webhook_url):
    """Invia proposta al Google Apps Script webhook"""
    try:
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
            "allegato": proposta_data['ALLEGATO'],
            "motivazione": proposta_data['MOTIVAZIONE'],
            "link": proposta_data['LINK'],
            "immagine": proposta_data['IMMAGINE'],
            "valuta": proposta_data['VALUTA']
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


def vote_proposta_via_webhook(row_number, votante, voto, webhook_url):
    """Invia voto al Google Apps Script webhook"""
    try:
        payload = {
            "action": "vote",
            "row_number": row_number,
            "votante": votante,
            "voto": voto
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
    tab1, tab2, tab3 = st.tabs(["📊 Visualizza Proposte", "➕ Aggiungi Proposta", "🗳️ Vota Proposte"])
    
    # ==================== CARICA DATI (comune a tutti i tab) ====================
    try:
        with st.spinner("Caricamento proposte dal Google Sheet..."):
            df_proposte = load_sheet_csv_proposte(spreadsheet_id, gid_proposte)
        
        if df_proposte is None or df_proposte.empty:
            st.error("❌ Impossibile caricare il foglio 'Proposte'")
            st.info("💡 Verifica che il foglio sia pubblico")
            st.stop()
        
        # Definisci i nomi delle colonne attese
        expected_columns = [
            'DATA', 'RESPONSABILE', 'OPERAZIONE', 'STRUMENTO', 'QUANTITA',
            'PMC', 'SL', 'TP', 'ORIZZONTE TEMPORALE', 'ALLEGATO',
            'MOTIVAZIONE', 'LINK', 'IMMAGINE', 'VALUTA', 'ESITO',
            'GALLOZ', 'STE', 'GARGIU', 'ALE', 'GIACA'
        ]
        
        if len(df_proposte.columns) >= 20:
            df_proposte.columns = expected_columns
        else:
            st.warning(f"⚠️ Il foglio ha {len(df_proposte.columns)} colonne, ne servono 20")
        
        # Aggiungi colonna numero riga (per identificare la proposta nel voto)
        df_proposte['ROW_NUMBER'] = range(2, len(df_proposte) + 2)  # +2 perché riga 1 è header
        
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
        
    except Exception as e:
        st.error(f"❌ Errore nel caricamento: {str(e)}")
        st.stop()
    
    # ==================== TAB 1: VISUALIZZA PROPOSTE ====================
    with tab1:
        st.success(f"✅ {len(df_proposte)} proposte caricate con successo!")
        
        # FILTRI SIDEBAR
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🔍 Filtri")
        
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
        
        buysell_options = df_proposte['OPERAZIONE'].dropna().unique().tolist()
        buysell_filter = st.sidebar.multiselect(
            "Operazione",
            options=buysell_options,
            default=buysell_options
        )
        
        esito_options = st.sidebar.radio(
            "Stato Votazione",
            options=["Tutte", "Approvate (≥3)", "Respinte (<3)", "Non votate"],
            index=0
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
        
        if esito_options == "Approvate (≥3)":
            df_filtered = df_filtered[df_filtered['ESITO'] >= 3]
        elif esito_options == "Respinte (<3)":
            df_filtered = df_filtered[df_filtered['ESITO'] < 3]
        elif esito_options == "Non votate":
            df_filtered = df_filtered[df_filtered['ESITO'].isna()]
        
        df_filtered = df_filtered.sort_values('DATA', ascending=False).reset_index(drop=True)
        
        # GRAFICO
        st.markdown("---")
        st.subheader("📊 Proposte per Responsabile")
        
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
            
            fig_resp.update_traces(texttemplate='%{text}', textposition='outside')
            fig_resp.update_layout(
                plot_bgcolor='#0e1117',
                paper_bgcolor='#0e1117',
                font={'color': 'white'},
                xaxis={'title': dict(text='Numero Proposte', font=dict(color='white')), 'color': 'white', 'gridcolor': '#333333'},
                yaxis={'title': dict(text='', font=dict(color='white')), 'color': 'white'},
                height=400,
                showlegend=False
            )
            
            st.plotly_chart(fig_resp, use_container_width=True)
        
        # TABELLA
        st.markdown("---")
        st.subheader("📋 DETTAGLIO PROPOSTE")
        st.caption("🔽 Ordinate dalla più recente")
        
        df_display = df_filtered.copy()
        df_display['DATA'] = df_display['DATA'].apply(lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else '')
        df_display['ORIZZONTE TEMPORALE'] = df_display['ORIZZONTE TEMPORALE'].apply(lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else '')
        
        def color_esito(val):
            if pd.isna(val):
                return 'background-color: #555555; color: white; font-style: italic'
            if val >= 3:
                return 'background-color: #2ecc71; color: white; font-weight: bold'
            else:
                return 'background-color: #e74c3c; color: white; font-weight: bold'
        
        # ⭐ NASCONDI COLONNE SPECIFICHE ⭐
        colonne_nascoste = [
            'ROW_NUMBER', 'ALLEGATO', 'MOTIVAZIONE', 'LINK', 'IMMAGINE',
            'GALLOZ', 'STE', 'GARGIU', 'ALE', 'GIACA']
        
        # Seleziona solo le colonne da mostrare
        cols_to_display = [col for col in df_display.columns if col not in colonne_nascoste]
        
        styled_df = df_display[cols_to_display].style.map(color_esito, subset=['ESITO'])
        
        st.dataframe(styled_df, use_container_width=True, height=600, hide_index=True)

        
        # DETTAGLIO SINGOLA PROPOSTA
        st.markdown("---")
        st.subheader("🔍 Dettaglio Proposta")
        
        if len(df_filtered) > 0:
            strumenti_list = df_filtered['STRUMENTO'].tolist()
            date_list = df_filtered['DATA'].apply(lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else 'Data non disponibile').tolist()
            
            options = [f"{strumento} - {data}" for strumento, data in zip(strumenti_list, date_list)]
            
            selected_idx = st.selectbox("Seleziona una proposta", range(len(options)), format_func=lambda x: options[x])
            
            proposta = df_filtered.iloc[selected_idx]
            
            esito_val = proposta['ESITO']
            if pd.isna(esito_val):
                st.warning("⚠️ PROPOSTA NON ANCORA VOTATA")
            elif esito_val >= 3:
                st.success(f"✅ ESITO: {int(esito_val)} - PROPOSTA APPROVATA")
            else:
                st.error(f"❌ ESITO: {int(esito_val)} - PROPOSTA RESPINTA")
            
            col_det1, col_det2, col_det3 = st.columns(3)

            with col_det1:
                st.markdown("##### 📌 Informazioni Base")
                st.write(f"**Strumento:** {proposta['STRUMENTO']}")
                st.write(f"**Operazione:** {proposta['OPERAZIONE']}")
                st.write(f"**Responsabile:** {proposta['RESPONSABILE']}")
                data_proposta = proposta['DATA']
                if pd.notna(data_proposta):
                    st.write(f"**Data proposta:** {data_proposta.strftime('%d/%m/%Y')}")
            
            with col_det2:
                st.markdown("##### 💰 Dati Finanziari")
                st.write(f"**Quantità:** {proposta['QUANTITA']}")
                st.write(f"**PMC:** {proposta['PMC']}")
                st.write(f"**SL:** {proposta['SL']}")
                st.write(f"**TP:** {proposta['TP']}")
                st.write(f"**Valuta:** {proposta['VALUTA']}")
                try:
                    quantita_val = float(str(proposta['QUANTITA']).replace(',', '.'))
                    pmc_val = float(str(proposta['PMC']).replace(',', '.'))
                    valore_totale = quantita_val * pmc_val
                    if proposta['VALUTA'] != "EUR":
                        exchange_rate = get_exchange_rate(proposta['VALUTA'], 'EUR')
                        valore_eur = valore_totale * exchange_rate
                        st.write(f"**Valore EUR:** € {valore_eur:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
                    else:
                        st.write(f"**Valore:** € {valore_totale:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
                except:
                    pass
            
            with col_det3:
                st.markdown("##### ✅ Votazione")
                if pd.notna(proposta['ESITO']):
                    st.write(f"**ESITO:** {int(proposta['ESITO'])} / 5")
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
            st.markdown("##### 📝 Motivazione")
            st.info(proposta['MOTIVAZIONE'] if pd.notna(proposta['MOTIVAZIONE']) else "Nessuna motivazione fornita")
            
            st.markdown("##### 📅 Orizzonte Temporale")
            orizzonte = proposta['ORIZZONTE TEMPORALE']
            if pd.notna(orizzonte):
                st.write(orizzonte.strftime('%d/%m/%Y'))
            else:
                st.write("Non specificato")
            
            col_link1, col_link2 = st.columns(2)
            
            with col_link1:
                if pd.notna(proposta['LINK']) and proposta['LINK']:
                    st.markdown(f"##### 🔗 [Apri Link]({proposta['LINK']})")
            
            with col_link2:
                if pd.notna(proposta['IMMAGINE']) and proposta['IMMAGINE']:
                    st.markdown(f"##### 🖼️ [Visualizza Immagine]({proposta['IMMAGINE']})")
        
        # EXPORT CSV
        st.markdown("---")
        csv = df_display[cols_to_display].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Scarica Proposte Filtrate (CSV)",
            data=csv,
            file_name=f"proposte_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    # ==================== TAB 2: AGGIUNGI PROPOSTA ====================
    with tab2:
        st.subheader("➕ Aggiungi Nuova Proposta")
        st.markdown("---")
        
        with st.form("new_proposta_form", clear_on_submit=True):
            st.markdown("### 📝 Dettagli Proposta")
            
            col1, col2 = st.columns(2)
            
            with col1:
                responsabili = st.multiselect(
                    "Responsabile/i Proposta *",
                    options=["Galloz", "Ste", "Gargiu", "Ale", "Giaca"]
                )
                
                buy_sell = st.selectbox("Operazione *", options=["Buy", "Sell"])
                strumento = st.text_input("Strumento *", placeholder="Es: AAPL, BTC-USD")
                quantita = st.number_input("Quantità *", min_value=0.0, value=0.0, step=0.01, format="%.4f")
                pmc = st.number_input("PMC *", min_value=0.0, value=0.0, step=0.01, format="%.4f")
            
            with col2:
                sl = st.number_input("Stop Loss", min_value=0.0, value=0.0, step=0.01, format="%.4f")
                tp = st.number_input("Take Profit", min_value=0.0, value=0.0, step=0.01, format="%.4f")
                valuta = st.selectbox("Valuta *", options=["EUR", "USD", "GBP", "JPY", "AUD", "CAD"])
                orizzonte = st.date_input("Orizzonte Temporale", value=None)
                allegato_tipo = st.selectbox("Tipo Allegato", options=["", "LINK", "IMMAGINE"])
            
            motivazione = st.text_area("Motivazione *", height=100)
            
            col_all1, col_all2 = st.columns(2)
            with col_all1:
                link = st.text_input("Link (URL)")
            with col_all2:
                immagine = st.text_input("Immagine (URL)")
            

                valore_totale = quantita * pmc
                if valuta != "EUR":
                    exchange_rate = get_exchange_rate(valuta, 'EUR')
                    valore_eur = valore_totale * exchange_rate
                    st.write(f"**Valore EUR:** € {valore_eur:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
                else:
                    st.write(f"**Valore:** € {valore_totale:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))

            st.markdown("---")
            submitted = st.form_submit_button("💾 Salva Proposta", type="primary", use_container_width=True)
        
        if submitted:
            errors = []
            if not responsabili:
                errors.append("⚠️ Seleziona almeno un responsabile")
            if not strumento:
                errors.append("⚠️ Il campo 'Strumento' è obbligatorio")
            if quantita <= 0:
                errors.append("⚠️ La 'Quantità' deve essere maggiore di 0")
            if pmc <= 0:
                errors.append("⚠️ Il 'PMC' deve essere maggiore di 0")
            if not motivazione:
                errors.append("⚠️ La 'Motivazione' è obbligatoria")
            
            if errors:
                for error in errors:
                    st.error(error)
            else:
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
                    'MOTIVAZIONE': motivazione,
                    'LINK': link,
                    'IMMAGINE': immagine,
                    'VALUTA': valuta
                }
                
                with st.spinner("💾 Salvataggio proposta in corso..."):
                    success, message = append_proposta_via_webhook(new_proposta, WEBHOOK_URL)
                
                if success:
                    st.success(f"✅ {message}")
                    st.balloons()
                    st.cache_data.clear()
                    st.info("🔄 Torna al tab 'Visualizza Proposte' e clicca 'Aggiorna'")
                else:
                    st.error(f"❌ {message}")
    
    # ==================== TAB 3: VOTA PROPOSTE ====================
    with tab3:
        st.subheader("🗳️ Vota le Proposte")
        st.markdown("---")
        
        # Selezione votante
        votante = st.selectbox(
            "Chi sei?",
            options=["", "GALLOZ", "STE", "GARGIU", "ALE", "GIACA"],
            help="Seleziona il tuo nome per votare"
        )
        
        if not votante:
            st.info("👆 Seleziona il tuo nome per iniziare a votare")
            st.stop()
        
        st.markdown(f"### Ciao **{votante}**! 👋")
        st.caption("Vota le proposte qui sotto")
        
                # ⭐ FILTRA PROPOSTE: Non votate + Massimo 3 giorni fa ⭐
        from datetime import timedelta
        
        # Calcola la data limite (3 giorni fa)
        data_limite = pd.Timestamp.now() - timedelta(days=3)
        
        proposte_da_votare = df_proposte[
            # Condizione 1: Non hai ancora votato
            ((df_proposte[votante].isna()) | (df_proposte[votante].astype(str).str.strip() == '')) &
            # Condizione 2: Proposta inserita negli ultimi 3 giorni
            (df_proposte['DATA'] >= data_limite)
        ].copy()

        
        if len(proposte_da_votare) == 0:
            st.success("🎉 Hai già votato tutte le proposte disponibili!")
            st.stop()
        
        st.info(f"📊 **{len(proposte_da_votare)}** proposte da votare")
        
        # Mostra ogni proposta con form di voto
        for idx, proposta in proposte_da_votare.iterrows():
            with st.expander(f"🔹 {proposta['STRUMENTO']} - {proposta['OPERAZIONE']} ({proposta['DATA'].strftime('%d/%m/%Y') if pd.notna(proposta['DATA']) else 'N/A'})"):
                
                col_info1, col_info2 = st.columns(2)
                
                with col_info1:
                    st.write(f"**Responsabile:** {proposta['RESPONSABILE']}")
                    st.write(f"**Quantità:** {proposta['QUANTITA']}")
                    st.write(f"**PMC:** {proposta['PMC']}")
                    st.write(f"**Valuta:** {proposta['VALUTA']}")
                    try:
                        quantita_val = float(str(proposta['QUANTITA']).replace(',', '.'))
                        pmc_val = float(str(proposta['PMC']).replace(',', '.'))
                        valore_totale = quantita_val * pmc_val
                        if proposta['VALUTA'] != "EUR":
                            exchange_rate = get_exchange_rate(proposta['VALUTA'], 'EUR')
                            valore_eur = valore_totale * exchange_rate
                            st.write(f"**Valore EUR:** € {valore_eur:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
                        else:
                            st.write(f"**Valore:** € {valore_totale:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
                    except:
                        pass
                
                with col_info2:
                    st.write(f"**SL:** {proposta['SL']}")
                    st.write(f"**TP:** {proposta['TP']}")
                    orizzonte_str = proposta['ORIZZONTE TEMPORALE'].strftime('%d/%m/%Y') if pd.notna(proposta['ORIZZONTE TEMPORALE']) else 'N/A'
                    st.write(f"**Orizzonte:** {orizzonte_str}")
                
                st.markdown("**Motivazione:**")
                st.info(proposta['MOTIVAZIONE'] if pd.notna(proposta['MOTIVAZIONE']) else "N/A")
                
                # Mostra voti già espressi
                voti_attuali = []
                for nome in ['GALLOZ', 'STE', 'GARGIU', 'ALE', 'GIACA']:
                    voto_val = str(proposta[nome]).lower().strip()
                    if voto_val == 'x':
                        voti_attuali.append(f"✅ {nome}")
                    elif voto_val == 'o':
                        voti_attuali.append(f"❌ {nome}")
                
                if voti_attuali:
                    st.caption("Voti espressi: " + " | ".join(voti_attuali))
                
                # Form voto
                col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
                
                with col_btn1:
                    if st.button("✅ Favorevole", key=f"fav_{proposta['ROW_NUMBER']}", use_container_width=True):
                        with st.spinner("Invio voto..."):
                            success, message = vote_proposta_via_webhook(
                                proposta['ROW_NUMBER'],
                                votante,
                                'x',
                                WEBHOOK_URL
                            )
                        if success:
                            st.success(message)
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(message)
                
                with col_btn2:
                    if st.button("❌ Contrario", key=f"con_{proposta['ROW_NUMBER']}", use_container_width=True):
                        with st.spinner("Invio voto..."):
                            success, message = vote_proposta_via_webhook(
                                proposta['ROW_NUMBER'],
                                votante,
                                'o',
                                WEBHOOK_URL
                            )
                        if success:
                            st.success(message)
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(message)
