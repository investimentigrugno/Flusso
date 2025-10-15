import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection

def portfolio_tracker_app():
    """Applicazione Portfolio Tracker"""
    
    st.title("📊 Portfolio Tracker")
    st.markdown("---")
    
    # URL del foglio Google Sheets
    sheet_url = "https://docs.google.com/spreadsheets/d/1mD9jxDJv26aZwCdIbvQVjlJGBhRwKWwQnPpPPq0ON5Y"
    
    # Opzioni nella sidebar
    st.sidebar.markdown("### ⚙️ Opzioni Portfolio")
    show_metrics = st.sidebar.checkbox("Mostra metriche", value=False)
    
    # Bottone per aggiornare i dati manualmente
    if st.sidebar.button("🔄 Aggiorna Dati", type="primary"):
        st.cache_data.clear()
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.caption("💡 Clicca 'Aggiorna Dati' per ricaricare i dati dal foglio Google")
    
    try:
        # Inizializza connessione a Google Sheets
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        with st.spinner("Caricamento dati dal Google Sheet..."):
            # Carica foglio "Portfolio" (tabella principale con asset)
            df = conn.read(
                spreadsheet=sheet_url,
                worksheet="Portfolio",
                ttl=60  # Cache per 60 secondi
            )
            
            # Carica foglio "dati" (per i grafici temporali)
            df_dati = conn.read(
                spreadsheet=sheet_url,
                worksheet="dati",
                ttl=60
            )
        
        # Verifica che i dati siano stati caricati correttamente
        if df is None or df.empty:
            st.error("❌ Il foglio 'Portfolio' è vuoto o non è stato caricato correttamente.")
            st.stop()
        
        if df_dati is None or df_dati.empty:
            st.warning("⚠️ Il foglio 'dati' è vuoto o non è stato caricato correttamente. I grafici temporali non saranno disponibili.")
        
        # Tabella principale (prime 16 righe e 13 colonne)
        df_filtered = df.iloc[:16, :13]
        
        # Tabella dati principali forzando manualmente intestazioni
        df_summary = df.iloc[18:19, 3:12].copy()
        
        # Definisci manualmente i nomi delle colonne
        summary_headers = [
            "DEPOSIT", "VALUE €", "P&L %", "P&L TOT", "P&L % LIVE", 
            "P&L LIVE", "TOT $", "EUR/USD", "TOT €"
        ]
        df_summary.columns = summary_headers
        
        st.success("✅ Dati caricati con successo!")
        
        # ==================== SEZIONE TABELLE ====================
        st.markdown("---")
        st.subheader("💼 Dati Principali del Portafoglio")
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
        
        st.subheader("Portfolio Completo")
        st.dataframe(df_filtered, use_container_width=True, height=600, hide_index=True)
        
        # Print in console per debug
        print("\n" + "="*100)
        print("TABELLA PORTFOLIO COMPLETA")
        print("="*100)
        print(df_filtered.to_string())
        print("\n" + "="*100)
        
        print("\n" + "="*100)
        print("DATI PRINCIPALI PORTAFOGLIO")
        print("="*100)
        print(df_summary.to_string())
        print("\n" + "="*100)
        
        # ==================== GRAFICO 1: DISTRIBUZIONE VALORE PORTFOLIO ====================
        st.markdown("---")
        st.subheader("Distribuzione Valore Portfolio")
        
        df_chart = df_filtered[['NAME', 'VALUE']].copy()
        df_chart['VALUE_CLEAN'] = df_chart['VALUE'].str.replace('€', '').str.replace('.', '').str.replace(',', '.').str.strip()
        df_chart['VALUE_NUMERIC'] = pd.to_numeric(df_chart['VALUE_CLEAN'], errors='coerce')
        df_chart = df_chart[df_chart['VALUE_NUMERIC'] > 0].dropna()
        
        fig = px.pie(
            df_chart, 
            values='VALUE_NUMERIC', 
            names='NAME',
            title='Distribuzione del Valore per Asset',
            hole=0.3
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
                yanchor="top",
                y=-0.1,
                xanchor="center",
                x=0.5,
                font=dict(size=10)
            ),
            margin=dict(l=20, r=20, t=80, b=150)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # ==================== GRAFICO 2: DISTRIBUZIONE PER TIPO DI ASSET ====================
        st.markdown("---")
        st.subheader("💰 Distribuzione Valore per Tipo di Asset")
        
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
            title='Valore Totale per Categoria di Asset',
            hole=0.3,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        
        fig_asset_type.update_traces(
            textposition='none',
            hovertemplate='<b>%{label}</b><br>Valore: €%{value:,.2f}<br>Percentuale: %{percent}<extra></extra>'
        )
        
        fig_asset_type.update_layout(
            showlegend=True,
            height=700,
            legend=dict(
                orientation="v",
                yanchor="middle",
                y=0.5,
                xanchor="left",
                x=1.02,
                font=dict(size=11)
            )
        )
        
        st.plotly_chart(fig_asset_type, use_container_width=True)
        
        # ==================== GRAFICO 3: DISTRIBUZIONE POSIZIONI L/B/P ====================
        st.markdown("---")
        st.subheader("Distribuzione Valore per Tipo di Posizione")
        
        df_pos_value = df_filtered[['LUNGO/BREVE', 'VALUE']].copy()
        df_pos_value = df_pos_value[df_pos_value['LUNGO/BREVE'].notna() & (df_pos_value['LUNGO/BREVE'] != '')]
        
        df_pos_value['VALUE_CLEAN'] = df_pos_value['VALUE'].str.replace('€', '').str.replace('.', '').str.replace(',', '.').str.strip()
        df_pos_value['VALUE_NUMERIC'] = pd.to_numeric(df_pos_value['VALUE_CLEAN'], errors='coerce')
        df_pos_value = df_pos_value[df_pos_value['VALUE_NUMERIC'] > 0].dropna()
        
        pos_value_agg = df_pos_value.groupby('LUNGO/BREVE')['VALUE_NUMERIC'].sum().reset_index()
        pos_value_agg.columns = ['Posizione', 'Valore']
        
        position_map = {
            'L': 'Lungo',
            'B': 'Breve', 
            'P': 'Passività'
        }
        pos_value_agg['Posizione'] = pos_value_agg['Posizione'].map(position_map)
        
        fig_pos_value = px.pie(
            pos_value_agg,
            values='Valore',
            names='Posizione',
            title='Valore Totale per Posizione (L/B/P)',
            hole=0.3,
            color_discrete_sequence=['#2ecc71', '#e74c3c', '#f39c12']
        )
        
        fig_pos_value.update_traces(
            textposition='none',
            hovertemplate='<b>%{label}</b><br>Valore: €%{value:,.2f}<br>Percentuale: %{percent}<extra></extra>'
        )
        
        fig_pos_value.update_layout(
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="middle",
                y=0.5,
                xanchor="left",
                x=1.02,
                font=dict(size=11)
            )
        )
        
        st.plotly_chart(fig_pos_value, use_container_width=True)
        
        # ==================== GRAFICO 4: ANDAMENTO P&L NEL TEMPO ====================
        if df_dati is not None and not df_dati.empty:
            st.markdown("---")
            st.subheader("📈 Andamento P&L nel Tempo")
            
            try:
                # Estrai colonne: col 10=DATA, col 3=P&L%, col 12=SMA9%, col 13=SMA20%
                df_chart_data = df_dati.iloc[:, [9, 2, 11, 12]].copy()
                df_chart_data.columns = ['Data', 'P&L%', 'SMA9%', 'SMA20%']
                
                # Converti Data
                df_chart_data['Data'] = pd.to_datetime(df_chart_data['Data'], errors='coerce')
                df_chart_data = df_chart_data.dropna(subset=['Data'])
                
                # Filtra solo dati dal 2025
                df_chart_data = df_chart_data[df_chart_data['Data'] >= '2025-01-01']
                
                # Funzione per pulire percentuali
                def clean_percentage(col):
                    if col.dtype == 'object':
                        col = col.str.replace('%', '').str.replace(',', '.').str.strip()
                    return pd.to_numeric(col, errors='coerce')
                
                df_chart_data['P&L%'] = clean_percentage(df_chart_data['P&L%'])
                df_chart_data['SMA9%'] = clean_percentage(df_chart_data['SMA9%'])
                df_chart_data['SMA20%'] = clean_percentage(df_chart_data['SMA20%'])
                
                df_chart_data = df_chart_data.dropna()
                df_chart_data = df_chart_data.sort_values('Data')
                
                if len(df_chart_data) == 0:
                    st.warning("⚠️ Nessun dato disponibile per il 2025.")
                else:
                    fig_combined = go.Figure()
                    
                    # Barre P&L%
                    fig_combined.add_trace(go.Bar(
                        x=df_chart_data['Data'],
                        y=df_chart_data['P&L%'],
                        name='P&L %',
                        marker_color='#3498db',
                        hovertemplate='<b>Data:</b> %{x|%d/%m/%Y}<br><b>P&L:</b> %{y:.2f}%<extra></extra>'
                    ))
                    
                    # Linea SMA9%
                    fig_combined.add_trace(go.Scatter(
                        x=df_chart_data['Data'],
                        y=df_chart_data['SMA9%'],
                        name='SMA9 %',
                        mode='lines+markers',
                        line=dict(color='#e74c3c', width=2),
                        marker=dict(size=4),
                        hovertemplate='<b>Data:</b> %{x|%d/%m/%Y}<br><b>SMA9:</b> %{y:.2f}%<extra></extra>'
                    ))
                    
                    # Linea SMA20%
                    fig_combined.add_trace(go.Scatter(
                        x=df_chart_data['Data'],
                        y=df_chart_data['SMA20%'],
                        name='SMA20 %',
                        mode='lines+markers',
                        line=dict(color='#2ecc71', width=2),
                        marker=dict(size=4),
                        hovertemplate='<b>Data:</b> %{x|%d/%m/%Y}<br><b>SMA20:</b> %{y:.2f}%<extra></extra>'
                    ))
                    
                    # Linea 0%
                    fig_combined.add_hline(
                        y=0, 
                        line_dash="dash", 
                        line_color="gray", 
                        opacity=0.5,
                        annotation_text="0%",
                        annotation_position="right"
                    )
                    
                    fig_combined.update_layout(
                        title=dict(
                            text='Andamento P&L % e Medie Mobili (SMA) - Anno 2025',
                            font=dict(color='white')
                        ),
                        xaxis=dict(
                            title=dict(text='Data', font=dict(color='white')),
                            showgrid=True,
                            gridcolor='#333333',
                            color='white'
                        ),
                        yaxis=dict(
                            title=dict(text='Percentuale (%)', font=dict(color='white')),
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
                        barmode='relative',
                        font=dict(color='white')
                    )
                    
                    st.plotly_chart(fig_combined, use_container_width=True)
                    
                    # Statistiche P&L
                    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                    
                    with col_stat1:
                        st.metric("Ultimo P&L %", f"{df_chart_data['P&L%'].iloc[-1]:.2f}%")
                    with col_stat2:
                        st.metric("Media P&L %", f"{df_chart_data['P&L%'].mean():.2f}%")
                    with col_stat3:
                        st.metric("Max P&L %", f"{df_chart_data['P&L%'].max():.2f}%")
                    with col_stat4:
                        st.metric("Min P&L %", f"{df_chart_data['P&L%'].min():.2f}%")
                
            except Exception as e:
                st.warning(f"⚠️ Impossibile creare il grafico P&L: {str(e)}")
                with st.expander("🔍 Dettagli errore"):
                    st.code(str(e))
        
        # ==================== GRAFICO 5: VOLATILITÀ ====================
        if df_dati is not None and not df_dati.empty:
            st.markdown("---")
            st.subheader("📉 Volatilità del Portfolio")
            
            try:
                # Estrai colonne: col 3=DATA, col 14=Vol Breve, col 15=Vol Lungo
                df_vol_data = df_dati.iloc[:, [2, 13, 14]].copy()
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
                    st.warning("⚠️ Nessun dato di volatilità disponibile per il 2025.")
                else:
                    fig_volatility = go.Figure()
                    
                    # Volatilità Breve
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
                    
                    # Volatilità Lungo
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
                        title=dict(
                            text='Volatilità a Breve e Lungo Termine - Anno 2025',
                            font=dict(color='white')
                        ),
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
                    
                    # Statistiche Volatilità
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
                st.warning(f"⚠️ Impossibile creare il grafico di volatilità: {str(e)}")
                with st.expander("🔍 Dettagli errore"):
                    st.code(str(e))
        
        # ==================== METRICHE OPZIONALI ====================
        if show_metrics:
            st.markdown("---")
            st.subheader("📊 Statistiche Portfolio")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Totale Asset", len(df_filtered))
            
            with col2:
                asset_types = df_filtered['ASSET'].value_counts()
                st.metric("Categorie Asset", len(asset_types))
            
            with col3:
                st.metric("Righe", df_filtered.shape[0])
            
            with col4:
                st.metric("Colonne", df_filtered.shape[1])
            
            st.markdown("---")
            st.subheader("📈 Distribuzione Asset")
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.write("**Asset per categoria:**")
                asset_counts = df_filtered['ASSET'].value_counts()
                for asset_type, count in asset_counts.items():
                    st.write(f"• {asset_type}: {count}")
            
            with col_b:
                st.write("**Posizioni (Lungo/Breve):**")
                position_counts = df_filtered['LUNGO/BREVE'].value_counts()
                for position, count in position_counts.items():
                    if position:
                        st.write(f"• {position}: {count}")
    
    except Exception as e:
        st.error(f"❌ Errore nel caricamento dei dati: {str(e)}")
        st.info("💡 Verifica che il foglio Google Sheets sia pubblicamente accessibile e che i fogli 'Portfolio' e 'dati' esistano.")
        
        with st.expander("🔍 Dettagli errore"):
            st.code(str(e))
