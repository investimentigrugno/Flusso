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
        
        # ==================== METRICHE RIEPILOGATIVE ====================
        st.markdown("---")
        st.subheader("📊 Riepilogo")
        
        col_t1, col_t2, col_t3, col_t4 = st.columns(4)
        
        with col_t1:
            st.metric("Totale Transazioni", len(df_filtered_trans))
        
        with col_t2:
            # Somma commissioni
            df_filtered_trans['Commissioni_num'] = pd.to_numeric(
                df_filtered_trans['Commissioni'].astype(str).str.replace('€', '').str.replace('.', '').str.replace(',', '.').str.strip(), 
                errors='coerce'
            )
            totale_commissioni = df_filtered_trans['Commissioni_num'].sum()
            st.metric("Totale Commissioni", f"€{totale_commissioni:,.2f}")
        
        with col_t3:
            # Controvalore totale
            df_filtered_trans['Controvalore_num'] = pd.to_numeric(
                df_filtered_trans['Controvalore €'].astype(str).str.replace('€', '').str.replace('.', '').str.replace(',', '.').str.strip(), 
                errors='coerce'
            )
            controvalore_totale = df_filtered_trans['Controvalore_num'].sum()
            st.metric("Controvalore Totale", f"€{controvalore_totale:,.2f}")
        
        with col_t4:
            strumenti_unici_filtered = df_filtered_trans['Strumento'].nunique()
            st.metric("Strumenti Diversi", strumenti_unici_filtered)
        
        # ==================== TABELLA TRANSAZIONI ====================
        st.markdown("---")
        st.subheader("📋 Dettaglio Transazioni")
        
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
        
        # ==================== GRAFICI ANALISI ====================
        st.markdown("---")
        st.subheader("📈 Analisi Transazioni")
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("#### Transazioni per Tipo")
            
            # Conteggio per tipo di operazione
            op_counts = df_filtered_trans['Operazione'].value_counts().reset_index()
            op_counts.columns = ['Operazione', 'Conteggio']
            
            fig_op = px.bar(
                op_counts,
                x='Operazione',
                y='Conteggio',
                title='',
                color='Operazione',
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            
            fig_op.update_layout(
                showlegend=False,
                height=400,
                plot_bgcolor='#0e1117',
                paper_bgcolor='#0e1117',
                font=dict(color='white'),
                xaxis=dict(
                    title=dict(text='Tipo Operazione', font=dict(color='white')), 
                    color='white',
                    gridcolor='#333333'
                ),
                yaxis=dict(
                    title=dict(text='Numero Transazioni', font=dict(color='white')), 
                    color='white', 
                    gridcolor='#333333'
                )
            )
            
            st.plotly_chart(fig_op, use_container_width=True)
        
        with col_chart2:
            st.markdown("#### Top 10 Strumenti")
            
            # Top 10 strumenti per controvalore
            df_strumenti = df_filtered_trans.groupby('Strumento')['Controvalore_num'].sum().reset_index()
            df_strumenti.columns = ['Strumento', 'Controvalore']
            df_strumenti = df_strumenti.sort_values('Controvalore', ascending=False).head(10)
            
            fig_strumenti = px.bar(
                df_strumenti,
                x='Controvalore',
                y='Strumento',
                orientation='h',
                title='',
                color='Controvalore',
                color_continuous_scale='Blues'
            )
            
            fig_strumenti.update_layout(
                showlegend=False,
                height=400,
                plot_bgcolor='#0e1117',
                paper_bgcolor='#0e1117',
                font=dict(color='white'),
                xaxis=dict(
                    title=dict(text='Controvalore (€)', font=dict(color='white')), 
                    color='white', 
                    gridcolor='#333333'
                ),
                yaxis=dict(
                    title=dict(text='', font=dict(color='white')), 
                    color='white'
                )
            )
            
            st.plotly_chart(fig_strumenti, use_container_width=True)
        
        # ==================== GRAFICO COMMISSIONI MENSILI ====================
        st.markdown("---")
        st.subheader("💰 Andamento Commissioni")
        
        # Aggrega commissioni per mese
        df_filtered_trans['Mese'] = df_filtered_trans['Data'].dt.to_period('M').dt.to_timestamp()
        commissioni_mensili = df_filtered_trans.groupby('Mese')['Commissioni_num'].sum().reset_index()
        commissioni_mensili.columns = ['Mese', 'Commissioni']
        commissioni_mensili = commissioni_mensili.sort_values('Mese')
        
        fig_commissioni = go.Figure()
        
        fig_commissioni.add_trace(go.Scatter(
            x=commissioni_mensili['Mese'],
            y=commissioni_mensili['Commissioni'],
            mode='lines+markers',
            name='Commissioni Mensili',
            line=dict(color='#e74c3c', width=3),
            marker=dict(size=8),
            fill='tozeroy',
            fillcolor='rgba(231, 76, 60, 0.2)',
            hovertemplate='<b>Mese:</b> %{x|%B %Y}<br><b>Commissioni:</b> €%{y:.2f}<extra></extra>'
        ))
        
        fig_commissioni.update_layout(
            title=dict(text='', font=dict(color='white')),
            xaxis=dict(
                title=dict(text='Mese', font=dict(color='white')), 
                showgrid=True, 
                gridcolor='#333333', 
                color='white'
            ),
            yaxis=dict(
                title=dict(text='Commissioni (€)', font=dict(color='white')), 
                showgrid=True, 
                gridcolor='#333333', 
                color='white'
            ),
            height=400,
            plot_bgcolor='#0e1117',
            paper_bgcolor='#0e1117',
            font=dict(color='white'),
            hovermode='x unified'
        )
        
        st.plotly_chart(fig_commissioni, use_container_width=True)
        
        # ==================== GRAFICO CONTROVALORE PER VALUTA ====================
        st.markdown("---")
        st.subheader("🌍 Distribuzione per Valuta")
        
        col_val1, col_val2 = st.columns(2)
        
        with col_val1:
            # Torta distribuzione per valuta
            valuta_dist = df_filtered_trans.groupby('Valuta')['Controvalore_num'].sum().reset_index()
            valuta_dist.columns = ['Valuta', 'Controvalore']
            valuta_dist = valuta_dist[valuta_dist['Controvalore'] > 0]
            
            fig_valuta = px.pie(
                valuta_dist,
                values='Controvalore',
                names='Valuta',
                title='Controvalore per Valuta',
                hole=0.3,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            
            fig_valuta.update_traces(
                textposition='inside',
                textinfo='percent+label',
                hovertemplate='<b>%{label}</b><br>Controvalore: €%{value:,.2f}<br>Percentuale: %{percent}<extra></extra>'
            )
            
            fig_valuta.update_layout(
                height=400,
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.1,
                    xanchor="center",
                    x=0.5,
                    font=dict(size=10, color='white')
                ),
                font=dict(color='white'),
                paper_bgcolor='#0e1117'
            )
            
            st.plotly_chart(fig_valuta, use_container_width=True)
        
        with col_val2:
            # Conteggio transazioni per valuta
            valuta_count = df_filtered_trans['Valuta'].value_counts().reset_index()
            valuta_count.columns = ['Valuta', 'Transazioni']
            
            fig_val_count = px.bar(
                valuta_count,
                x='Valuta',
                y='Transazioni',
                title='Numero Transazioni per Valuta',
                color='Transazioni',
                color_continuous_scale='Greens'
            )
            
            fig_val_count.update_layout(
                showlegend=False,
                height=400,
                plot_bgcolor='#0e1117',
                paper_bgcolor='#0e1117',
                font=dict(color='white'),
                xaxis=dict(
                    title=dict(text='Valuta', font=dict(color='white')), 
                    color='white'
                ),
                yaxis=dict(
                    title=dict(text='Numero Transazioni', font=dict(color='white')), 
                    color='white', 
                    gridcolor='#333333'
                )
            )
            
            st.plotly_chart(fig_val_count, use_container_width=True)
        
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
