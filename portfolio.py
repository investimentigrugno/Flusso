import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time


@st.cache_data(ttl=120)
def load_sheet_csv(spreadsheet_id, gid):
    """Carica foglio pubblico via CSV export"""
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    
    # Retry con backoff
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


def portfolio_tracker_app():
    """Applicazione Portfolio Tracker"""
    
    st.title("📊 Portfolio Tracker")
    st.markdown("---")
    
    # ID del foglio Google Sheets
    spreadsheet_id = "1mD9jxDJv26aZwCdIbvQVjlJGBhRwKWwQnPpPPq0ON5Y"
    gid_portfolio = 0  # Foglio Portfolio (dati strumenti)
    gid_portfolio_status = 1033121372  # ⭐ NUOVO: Foglio Portfolio_Status (dati principali)
    gid_dati = 1009022145  # Foglio dati storici
    
    # Opzioni nella sidebar
    st.sidebar.markdown("### ⚙️ Opzioni Portfolio")
    show_metrics = st.sidebar.checkbox("Mostra metriche", value=False)
    
    # Bottone refresh
    if st.sidebar.button("🔄 Aggiorna Dati", type="primary"):
        st.cache_data.clear()
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.caption("💡 I dati vengono aggiornati automaticamente ogni 2 minuti")
    
    try:
        with st.spinner("Caricamento dati dal Google Sheet..."):
            # Carica foglio Portfolio (strumenti)
            df = load_sheet_csv(spreadsheet_id, gid_portfolio)
            # ⭐ Carica foglio Portfolio_Status (dati principali)
            df_status = load_sheet_csv(spreadsheet_id, gid_portfolio_status)
            # Carica foglio dati storici
            df_dati = load_sheet_csv(spreadsheet_id, gid_dati)
        
        if df is None or df.empty:
            st.error("❌ Impossibile caricare il foglio 'Portfolio'")
            st.info("💡 Verifica che il foglio sia pubblico: Condividi → Chiunque con il link → Visualizzatore")
            st.stop()
        
        if df_status is None or df_status.empty:
            st.error("❌ Impossibile caricare il foglio 'Portfolio_Status'")
            st.info("💡 Verifica che il foglio sia pubblico: Condividi → Chiunque con il link → Visualizzatore")
            st.stop()
        
        # ⭐ CARICA DATI PRINCIPALI DAL NUOVO FOGLIO Portfolio_Status ⭐
        # Riga 1 = intestazioni (indice 0), Riga 2 = dati (indice 1)
        df_summary = df_status.iloc[0:1, :].copy()  # Prendi la riga 2 (indice 1)
        df_summary = df_summary.reset_index(drop=True)
        
        # ⭐ CARICA RIGHE PORTFOLIO FINO ALLA PRIMA COMPLETAMENTE VUOTA ⭐
        df_filtered = df.iloc[:, :13].copy()
        
        # Trova la prima riga completamente vuota
        prima_riga_vuota = None
        
        for i in range(len(df_filtered)):
            riga = df_filtered.iloc[i]
            tutte_vuote = True
            
            for valore in riga:
                if pd.notna(valore) and str(valore).strip() != '':
                    tutte_vuote = False
                    break
            
            if tutte_vuote:
                prima_riga_vuota = i
                break
        
        # Taglia alla prima riga vuota
        if prima_riga_vuota is not None and prima_riga_vuota > 0:
            df_filtered = df_filtered.iloc[:prima_riga_vuota]
        
        # Reset index
        df_filtered = df_filtered.reset_index(drop=True)
        
        st.success("✅ Dati caricati con successo!")
        
        # ==================== SEZIONE TABELLE ====================
        st.markdown("---")
        st.subheader("💼 Portfolio Status")
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
        
        st.subheader("Portfolio Completo")
        
        # Mostra il numero di strumenti
        st.caption(f"📊 {len(df_filtered)} strumenti in portafoglio")
        
        st.dataframe(df_filtered, use_container_width=True, height=600, hide_index=True)
        
        # Print console
        print("\n" + "="*100)
        print(f"TABELLA PORTFOLIO COMPLETA - {len(df_filtered)} STRUMENTI")
        print("="*100)
        print(df_filtered.to_string())
        print("\n" + "="*100)
        
        print("\n" + "="*100)
        print("PORTFOLIO STATUS")
        print("="*100)
        print(df_summary.to_string())
        print("\n" + "="*100)
        
        # ==================== GRAFICO 1: DISTRIBUZIONE VALORE ====================
        df_chart = df_filtered[['NAME', 'VALUE']].copy()
        df_chart['VALUE_CLEAN'] = df_chart['VALUE'].str.replace('€', '').str.replace('.', '').str.replace(',', '.').str.strip()
        df_chart['VALUE_NUMERIC'] = pd.to_numeric(df_chart['VALUE_CLEAN'], errors='coerce')
        df_chart = df_chart[df_chart['VALUE_NUMERIC'] > 0].dropna()
        
        fig = px.pie(
            df_chart,
            values='VALUE_NUMERIC',
            names='NAME',
            hole=0.5
        )
        
        fig.update_traces(
            textposition='none',
            hovertemplate='<b>%{label}</b><br>Valore: €%{value:,.2f}<br>Percentuale: %{percent}<extra></extra>'
        )
        
        fig.update_layout(
            showlegend=True,
            height=800,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.05,
                xanchor="auto",
                font=dict(size=14)
            ),
            margin=dict(l=20, r=20, t=80, b=150)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # ==================== GRAFICI 2 E 3: AFFIANCATI ====================
        st.markdown("---")
        
        col_left, col_right = st.columns(2)
        
        with col_left:
            # ==================== GRAFICO 2: TIPO ASSET ====================
            st.subheader("ASSET TYPES")
            
            df_asset_type = df_filtered[['ASSET', 'VALUE']].copy()
            df_asset_type = df_asset_type[df_asset_type['ASSET'].notna() & (df_asset_type['ASSET'] != '')]
            
            df_asset_type['VALUE_CLEAN'] = df_asset_type['VALUE'].str.replace('€', '').str.replace('.', '').str.replace(',', '.').str.strip()
            df_asset_type['VALUE_NUMERIC'] = pd.to_numeric(df_asset_type['VALUE_CLEAN'], errors='coerce')
            df_asset_type = df_asset_type[df_asset_type['VALUE_NUMERIC'] > 0].dropna()
            
            asset_type_agg = df_asset_type.groupby('ASSET')['VALUE_NUMERIC'].sum().reset_index()
            asset_type_agg.columns = ['Tipo Asset', 'Valore']
            asset_type_agg = asset_type_agg.sort_values('Valore', ascending=False)
            
            fig_asset_type = px.pie(
                asset_type_agg,
                values='Valore',
                names='Tipo Asset',
                hole=0.3,
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            
            fig_asset_type.update_traces(
                textposition='none',
                hovertemplate='<b>%{label}</b><br>Valore: €%{value:,.2f}<br>Percentuale: %{percent}<extra></extra>'
            )
            
            fig_asset_type.update_layout(
                showlegend=True,
                height=600,
                legend=dict(
                    orientation="h",
                    yanchor="auto",
                    y=-0.2,
                    xanchor="center",
                    x=0.5,
                    font=dict(size=14)
                )
            )
            
            st.plotly_chart(fig_asset_type, use_container_width=True)
        
        with col_right:
            # ==================== GRAFICO 3: POSIZIONI L/B/P ====================
            st.subheader("HORIZON OF POSITION")
            
            df_pos_value = df_filtered[['LUNGO/BREVE', 'VALUE']].copy()
            df_pos_value = df_pos_value[df_pos_value['LUNGO/BREVE'].notna() & (df_pos_value['LUNGO/BREVE'] != '')]
            
            df_pos_value['VALUE_CLEAN'] = df_pos_value['VALUE'].str.replace('€', '').str.replace('.', '').str.replace(',', '.').str.strip()
            df_pos_value['VALUE_NUMERIC'] = pd.to_numeric(df_pos_value['VALUE_CLEAN'], errors='coerce')
            df_pos_value = df_pos_value[df_pos_value['VALUE_NUMERIC'] > 0].dropna()
            
            pos_value_agg = df_pos_value.groupby('LUNGO/BREVE')['VALUE_NUMERIC'].sum().reset_index()
            pos_value_agg.columns = ['Posizione', 'Valore']
            
            position_map = {'L': 'LUNGO', 'B': 'BREVE', 'P': 'PASSIVITA'}
            pos_value_agg['Posizione'] = pos_value_agg['Posizione'].map(position_map)
            
            fig_pos_value = px.pie(
                pos_value_agg,
                values='Valore',
                names='Posizione',
                hole=0.3,
                color_discrete_sequence=['#2ecc71', '#e74c3c', '#f39c12']
            )
            
            fig_pos_value.update_traces(
                textposition='none',
                hovertemplate='<b>%{label}</b><br>Valore: €%{value:,.2f}<br>Percentuale: %{percent}<extra></extra>'
            )
            
            fig_pos_value.update_layout(
                showlegend=True,
                height=600,
                legend=dict(
                    orientation="h",
                    yanchor="auto",
                    y=-0.2,
                    xanchor="center",
                    x=0.5,
                    font=dict(size=14)
                )
            )
            
            st.plotly_chart(fig_pos_value, use_container_width=True)
        
        # ==================== GRAFICO 4: P&L TEMPORALE ====================
        if df_dati is not None and not df_dati.empty:
            st.markdown("---")
            st.subheader("📈 P&L - HISTORICAL DATA")
            
            try:
                df_chart_data = df_dati.iloc[:, [9, 2, 11, 12]].copy()
                df_chart_data.columns = ['Data', 'P&L%', 'SMA9', 'SMA20']
                
                df_chart_data['Data'] = pd.to_datetime(df_chart_data['Data'], errors='coerce')
                df_chart_data = df_chart_data.dropna(subset=['Data'])
                df_chart_data = df_chart_data[df_chart_data['Data'] >= '2025-01-01']
                
                def clean_percentage(col):
                    if col.dtype == 'object':
                        col = col.str.replace('%', '').str.replace(',', '.').str.strip()
                    return pd.to_numeric(col, errors='coerce')
                
                df_chart_data['P&L%'] = clean_percentage(df_chart_data['P&L%'])
                df_chart_data['SMA9'] = clean_percentage(df_chart_data['SMA9'])
                df_chart_data['SMA20'] = clean_percentage(df_chart_data['SMA20'])
                
                df_chart_data = df_chart_data.dropna()
                df_chart_data = df_chart_data.sort_values('Data')
                
                if len(df_chart_data) > 0:
                    fig_combined = go.Figure()
                    
                    fig_combined.add_trace(go.Bar(
                        x=df_chart_data['Data'],
                        y=df_chart_data['P&L%'],
                        name='P&L %',
                        marker_color='#3498db',
                        hovertemplate='<b>Data:</b> %{x|%d/%m/%Y}<br><b>P&L:</b> %{y:.2f}%<extra></extra>'
                    ))
                    
                    fig_combined.add_trace(go.Scatter(
                        x=df_chart_data['Data'],
                        y=df_chart_data['SMA9'],
                        name='SMA9',
                        mode='lines+markers',
                        line=dict(color='#e74c3c', width=2),
                        marker=dict(size=4),
                        hovertemplate='<b>Data:</b> %{x|%d/%m/%Y}<br><b>SMA9:</b> %{y:.2f}%<extra></extra>'
                    ))
                    
                    fig_combined.add_trace(go.Scatter(
                        x=df_chart_data['Data'],
                        y=df_chart_data['SMA20'],
                        name='SMA20',
                        mode='lines+markers',
                        line=dict(color='#2ecc71', width=2),
                        marker=dict(size=4),
                        hovertemplate='<b>Data:</b> %{x|%d/%m/%Y}<br><b>SMA20:</b> %{y:.2f}%<extra></extra>'
                    ))
                    
                    fig_combined.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
                    
                    fig_combined.update_layout(
                        xaxis=dict(title=dict(text='Data', font=dict(color='white')), showgrid=True, gridcolor='#333333', color='white'),
                        yaxis=dict(title=dict(text='Percentuale (%)', font=dict(color='white')), showgrid=True, gridcolor='#333333', ticksuffix='%', color='white'),
                        hovermode='x unified',
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color='white'), bgcolor='rgba(0,0,0,0.5)'),
                        height=600,
                        plot_bgcolor='#0e1117',
                        paper_bgcolor='#0e1117',
                        barmode='relative',
                        font=dict(color='white')
                    )
                    
                    st.plotly_chart(fig_combined, use_container_width=True)
                    
                    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                    
                    with col_stat1:
                        st.metric("Ultimo P&L %", f"{df_chart_data['P&L%'].iloc[-1]:.2f}%")
                    with col_stat2:
                        st.metric("Media P&L %", f"{df_chart_data['P&L%'].mean():.2f}%")
                    with col_stat3:
                        st.metric("Max P&L %", f"{df_chart_data['P&L%'].max():.2f}%")
                    with col_stat4:
                        st.metric("Min P&L %", f"{df_chart_data['P&L%'].min():.2f}%")
                else:
                    st.warning("⚠️ Nessun dato disponibile per il 2025")
            
            except Exception as e:
                st.warning(f"⚠️ Impossibile creare grafico P&L: {str(e)}")
        
        # ==================== GRAFICO 5: VOLATILITÀ ====================
        if df_dati is not None and not df_dati.empty:
            st.markdown("---")
            st.subheader("📉 PORTFOLIO VOLATILITY")
            
            try:
                df_vol_data = df_dati.iloc[:, [9, 13, 14]].copy()
                df_vol_data.columns = ['Data', 'Volatilità Breve', 'Volatilità Lungo']
                
                df_vol_data['Data'] = pd.to_datetime(df_vol_data['Data'], errors='coerce')
                df_vol_data = df_vol_data.dropna(subset=['Data'])
                df_vol_data = df_vol_data[df_vol_data['Data'] >= '2025-01-01']
                
                def clean_percentage(col):
                    if col.dtype == 'object':
                        col = col.str.replace('%', '').str.replace(',', '.').str.strip()
                    return pd.to_numeric(col, errors='coerce')
                
                df_vol_data['Volatilità Breve'] = clean_percentage(df_vol_data['Volatilità Breve'])
                df_vol_data['Volatilità Lungo'] = clean_percentage(df_vol_data['Volatilità Lungo'])
                
                df_vol_data = df_vol_data.dropna()
                df_vol_data = df_vol_data.sort_values('Data')
                
                if len(df_vol_data) == 0:
                    st.warning("⚠️ Nessun dato di volatilità disponibile per il 2025")
                else:
                    fig_volatility = go.Figure()
                    
                    fig_volatility.add_trace(go.Scatter(
                        x=df_vol_data['Data'],
                        y=df_vol_data['Volatilità Breve'],
                        name='Volatilità Breve Termine',
                        mode='lines',
                        line=dict(color='#e74c3c', width=2.5),
                        fill='tozeroy',
                        fillcolor='rgba(231, 76, 60, 0.2)',
                        hovertemplate='<b>Data:</b> %{x|%d/%m/%Y}<br><b>Vol. Breve:</b> %{y:.2f}%<extra></extra>'
                    ))
                    
                    fig_volatility.add_trace(go.Scatter(
                        x=df_vol_data['Data'],
                        y=df_vol_data['Volatilità Lungo'],
                        name='Volatilità Lungo Termine',
                        mode='lines',
                        line=dict(color='#3498db', width=2.5),
                        fill='tozeroy',
                        fillcolor='rgba(52, 152, 219, 0.2)',
                        hovertemplate='<b>Data:</b> %{x|%d/%m/%Y}<br><b>Vol. Lungo:</b> %{y:.2f}%<extra></extra>'
                    ))
                    
                    fig_volatility.update_layout(
                        xaxis=dict(
                            title=dict(text='Data', font=dict(color='white')),
                            showgrid=True,
                            gridcolor='#333333',
                            color='white'
                        ),
                        yaxis=dict(
                            title=dict(text='Volatilità (%)', font=dict(color='white')),
                            showgrid=True,
                            gridcolor='#333333',
                            ticksuffix='%',
                            color='white'
                        ),
                        hovermode='x unified',
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1,
                            font=dict(color='white'),
                            bgcolor='rgba(0,0,0,0.5)'
                        ),
                        height=600,
                        plot_bgcolor='#0e1117',
                        paper_bgcolor='#0e1117',
                        font=dict(color='white')
                    )
                    
                    st.plotly_chart(fig_volatility, use_container_width=True)
                    
                    col_vol1, col_vol2, col_vol3, col_vol4 = st.columns(4)
                    
                    with col_vol1:
                        st.metric("Ultima Vol. Breve", f"{df_vol_data['Volatilità Breve'].iloc[-1]:.2f}%")
                    with col_vol2:
                        st.metric("Ultima Vol. Lungo", f"{df_vol_data['Volatilità Lungo'].iloc[-1]:.2f}%")
                    with col_vol3:
                        st.metric("Media Vol. Breve", f"{df_vol_data['Volatilità Breve'].mean():.2f}%")
                    with col_vol4:
                        st.metric("Media Vol. Lungo", f"{df_vol_data['Volatilità Lungo'].mean():.2f}%")
            
            except Exception as e:
                st.warning(f"⚠️ Errore grafico volatilità: {str(e)}")
                with st.expander("🔍 Dettagli errore"):
                    st.code(str(e))
        
        # ==================== METRICHE ====================
        if show_metrics:
            st.markdown("---")
            st.subheader("📊 Statistiche Portfolio")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Totale Asset", len(df_filtered))
            with col2:
                st.metric("Categorie Asset", len(df_filtered['ASSET'].value_counts()))
            with col3:
                st.metric("Righe", df_filtered.shape[0])
            with col4:
                st.metric("Colonne", df_filtered.shape[1])
            
            st.markdown("---")
            st.subheader("📈 Distribuzione Asset")
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.write("**Asset per categoria:**")
                for asset_type, count in df_filtered['ASSET'].value_counts().items():
                    st.write(f"• {asset_type}: {count}")
            
            with col_b:
                st.write("**Posizioni (Lungo/Breve):**")
                for position, count in df_filtered['LUNGO/BREVE'].value_counts().items():
                    if position:
                        st.write(f"• {position}: {count}")
    
    except Exception as e:
        st.error(f"❌ Errore: {str(e)}")
        st.info("💡 Verifica che il foglio sia pubblico")
        
        with st.expander("🔍 Dettagli errore"):
            st.code(str(e))
