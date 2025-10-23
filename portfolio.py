import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import time

@st.cache_data(ttl=120)
def load_sheet_csv(spreadsheet_id, gid):
    """Carica foglio pubblico via CSV export"""
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    
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
    gid_portfolio = 0
    gid_portfolio_status = 1033121372
    gid_dati = 1009022145
    
    # Opzioni nella sidebar
    st.sidebar.markdown("### ⚙️ Opzioni Portfolio")
    show_metrics = st.sidebar.checkbox("Mostra metriche", value=False)
    show_debug = st.sidebar.checkbox("🔍 Debug: Info filtri", value=False)
    
    if st.sidebar.button("🔄 Aggiorna Dati", type="primary"):
        st.cache_data.clear()
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.caption("💡 I dati vengono aggiornati automaticamente ogni 2 minuti")
    
    try:
        with st.spinner("Caricamento dati dal Google Sheet..."):
            df = load_sheet_csv(spreadsheet_id, gid_portfolio)
            df_status = load_sheet_csv(spreadsheet_id, gid_portfolio_status)
            df_dati = load_sheet_csv(spreadsheet_id, gid_dati)
        
        if df is None or df.empty:
            st.error("❌ Impossibile caricare il foglio 'Portfolio'")
            st.stop()
        
        if df_status is None or df_status.empty:
            st.error("❌ Impossibile caricare il foglio 'Portfolio_Status'")
            st.stop()
        
        # ==================== FILTRAGGIO RIGHE VUOTE ====================
        df_original_len = len(df)
        
        # Step 1: Rimuovi righe completamente vuote
        df_filtered = df.dropna(how='all')
        removed_empty = df_original_len - len(df_filtered)
        
        # Step 2: Rimuovi righe dove TICKER (colonna C, indice 2) è vuoto
        if len(df_filtered.columns) >= 3:
            df_filtered = df_filtered[
                df_filtered.iloc[:, 2].notna() & 
                (df_filtered.iloc[:, 2].astype(str).str.strip() != '')
            ]
        removed_no_ticker = df_original_len - removed_empty - len(df_filtered)
        
        # Step 3: Rimuovi righe dove QTY (colonna F, indice 5) = 0 o vuota
        if len(df_filtered.columns) >= 6:
            def is_valid_qty(val):
                if pd.isna(val):
                    return False
                try:
                    qty = float(str(val).replace(',', '.'))
                    return qty > 0.0001
                except:
                    return False
            
            df_filtered = df_filtered[df_filtered.iloc[:, 5].apply(is_valid_qty)]
        
        removed_zero_qty = df_original_len - removed_empty - removed_no_ticker - len(df_filtered)
        
        # Reset index
        df_filtered = df_filtered.reset_index(drop=True)
        
        # Carica Portfolio Status
        df_summary = df_status.iloc[0:1, :].copy().reset_index(drop=True)
        
        st.success(f"✅ Dati caricati con successo! ({len(df_filtered)} posizioni attive)")
        
        # Debug info (opzionale)
        if show_debug and (removed_empty > 0 or removed_no_ticker > 0 or removed_zero_qty > 0):
            with st.expander(f"🔍 Righe filtrate: {removed_empty + removed_no_ticker + removed_zero_qty}"):
                st.write(f"• Righe completamente vuote: {removed_empty}")
                st.write(f"• Righe senza ticker: {removed_no_ticker}")
                st.write(f"• Righe con QTY = 0: {removed_zero_qty}")
                st.write(f"• **Righe valide finali: {len(df_filtered)}**")
        
        # ==================== SEZIONE TABELLE ====================
        st.markdown("---")
        st.subheader("💼 Portfolio Status")
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.subheader("📋 Portfolio Completo")
        st.caption(f"📊 {len(df_filtered)} strumenti in portafoglio")
        
        if len(df_filtered) > 0:
            st.dataframe(df_filtered, use_container_width=True, height=600, hide_index=True)
        else:
            st.info("📭 Nessuna posizione attiva nel portfolio")
        
        # ==================== GRAFICO 1: DISTRIBUZIONE VALORE ====================
        if len(df_filtered) > 0:
            st.markdown("---")
            st.subheader("📊 Distribuzione Valore Portfolio")
            
            df_chart = df_filtered[['NAME', 'VALUE']].copy()
            df_chart['VALUE_CLEAN'] = df_chart['VALUE'].str.replace('€', '').str.replace('.', '').str.replace(',', '.').str.strip()
            df_chart['VALUE_NUMERIC'] = pd.to_numeric(df_chart['VALUE_CLEAN'], errors='coerce')
            df_chart = df_chart[df_chart['VALUE_NUMERIC'] > 0].dropna()
            
            if len(df_chart) > 0:
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
                    legend=dict(
                        orientation="h",
                        yanchor="auto",
                        y=-0.3,
                        xanchor="auto",
                        x=0.5,
                        font=dict(size=14)
                    ),
                    height=800,
                    margin=dict(l=20, r=20, t=50, b=100)
                )
                
                st.plotly_chart(fig, use_container_width=True)
        
        # ==================== GRAFICI 2 E 3: AFFIANCATI ====================
        if len(df_filtered) > 0:
            st.markdown("---")
            col_left, col_right = st.columns(2)
            
            with col_left:
                st.subheader("ASSET TYPES")
                
                df_asset_type = df_filtered[['ASSET', 'VALUE']].copy()
                df_asset_type = df_asset_type[df_asset_type['ASSET'].notna() & (df_asset_type['ASSET'] != '')]
                df_asset_type['VALUE_CLEAN'] = df_asset_type['VALUE'].str.replace('€', '').str.replace('.', '').str.replace(',', '.').str.strip()
                df_asset_type['VALUE_NUMERIC'] = pd.to_numeric(df_asset_type['VALUE_CLEAN'], errors='coerce')
                df_asset_type = df_asset_type[df_asset_type['VALUE_NUMERIC'] > 0].dropna()
                
                if len(df_asset_type) > 0:
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
                            y=1.1,
                            xanchor="auto",
                            x=0.5,
                            font=dict(size=14)
                        ),
                        margin=dict(l=20, r=20, t=50, b=10)
                    )
                    
                    st.plotly_chart(fig_asset_type, use_container_width=True)
            
            with col_right:
                st.subheader("HORIZON OF POSITION")
                
                df_pos_value = df_filtered[['LUNGO/BREVE', 'VALUE']].copy()
                df_pos_value = df_pos_value[df_pos_value['LUNGO/BREVE'].notna() & (df_pos_value['LUNGO/BREVE'] != '')]
                df_pos_value['VALUE_CLEAN'] = df_pos_value['VALUE'].str.replace('€', '').str.replace('.', '').str.replace(',', '.').str.strip()
                df_pos_value['VALUE_NUMERIC'] = pd.to_numeric(df_pos_value['VALUE_CLEAN'], errors='coerce')
                df_pos_value = df_pos_value[df_pos_value['VALUE_NUMERIC'] > 0].dropna()
                
                if len(df_pos_value) > 0:
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
                            y=1.1,
                            xanchor="auto",
                            x=0.5,
                            font=dict(size=14)
                        ),
                        margin=dict(l=20, r=20, t=50, b=10)
                    )
                    
                    st.plotly_chart(fig_pos_value, use_container_width=True)
        
        # ==================== GRAFICO 4: P&L STORICO CON SMA ====================
        if df_dati is not None and not df_dati.empty:
            st.markdown("---")
            st.subheader("📈 P&L - Historical Data")
            
            try:
                df_chart_data = df_dati.iloc[:, [9, 2]].copy()
                df_chart_data.columns = ['Data', 'P&L%']
                
                df_chart_data['Data'] = pd.to_datetime(df_chart_data['Data'], errors='coerce')
                df_chart_data = df_chart_data.dropna(subset=['Data'])
                df_chart_data = df_chart_data[df_chart_data['Data'] >= '2025-01-01']
                
                if df_chart_data['P&L%'].dtype == 'object':
                    df_chart_data['P&L%'] = df_chart_data['P&L%'].str.replace('%', '').str.replace(',', '.').str.strip()
                
                df_chart_data['P&L%'] = pd.to_numeric(df_chart_data['P&L%'], errors='coerce')
                df_chart_data = df_chart_data.dropna()
                df_chart_data = df_chart_data.sort_values('Data')
                
                df_chart_data['SMA9'] = df_chart_data['P&L%'].rolling(window=9).mean()
                df_chart_data['SMA20'] = df_chart_data['P&L%'].rolling(window=20).mean()
                
                if len(df_chart_data) > 0:
                    fig_pl = go.Figure()
                    
                    fig_pl.add_trace(go.Bar(
                        x=df_chart_data['Data'],
                        y=df_chart_data['P&L%'],
                        name='P&L %',
                        marker_color='#3498db',
                        hovertemplate='<b>Data:</b> %{x|%d/%m/%Y}<br><b>P&L:</b> %{y:.2f}%<extra></extra>'
                    ))
                    
                    fig_pl.add_trace(go.Scatter(
                        x=df_chart_data['Data'],
                        y=df_chart_data['SMA9'],
                        name='SMA9',
                        mode='lines+markers',
                        line=dict(color='#e74c3c', width=2),
                        marker=dict(size=4)
                    ))
                    
                    fig_pl.add_trace(go.Scatter(
                        x=df_chart_data['Data'],
                        y=df_chart_data['SMA20'],
                        name='SMA20',
                        mode='lines+markers',
                        line=dict(color='#2ecc71', width=2),
                        marker=dict(size=4)
                    ))
                    
                    fig_pl.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
                    
                    fig_pl.update_layout(
                        xaxis=dict(title='Data', showgrid=True, gridcolor='#333333', color='white'),
                        yaxis=dict(title='P&L (%)', showgrid=True, gridcolor='#333333', ticksuffix='%', color='white'),
                        hovermode='x unified',
                        height=600,
                        plot_bgcolor='#0e1117',
                        paper_bgcolor='#0e1117',
                        font=dict(color='white'),
                        barmode='relative'
                    )
                    
                    st.plotly_chart(fig_pl, use_container_width=True)
                    
                    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                    
                    with col_stat1:
                        st.metric("Ultimo P&L", f"{df_chart_data['P&L%'].iloc[-1]:.2f}%")
                    with col_stat2:
                        st.metric("Media P&L", f"{df_chart_data['P&L%'].mean():.2f}%")
                    with col_stat3:
                        st.metric("Max P&L", f"{df_chart_data['P&L%'].max():.2f}%")
                    with col_stat4:
                        st.metric("Min P&L", f"{df_chart_data['P&L%'].min():.2f}%")
            
            except Exception as e:
                st.warning(f"⚠️ Impossibile creare grafico P&L: {str(e)}")
        
        # ==================== GRAFICO 5: VOLATILITÀ ====================
        if df_dati is not None and not df_dati.empty:
            st.markdown("---")
            st.subheader("📉 Portfolio Volatility (Close-to-Close)")
            
            try:
                df_volatility = df_chart_data[['Data', 'P&L%']].copy()
                df_volatility = df_volatility.sort_values('Data')
                df_volatility['Rendimento'] = df_volatility['P&L%'].diff()
                df_volatility['Volatility_10d'] = df_volatility['Rendimento'].rolling(window=10).std()
                df_volatility['Volatility_50d'] = df_volatility['Rendimento'].rolling(window=50).std()
                df_volatility['Volatility_10d_annual'] = df_volatility['Volatility_10d'] * np.sqrt(252)
                df_volatility['Volatility_50d_annual'] = df_volatility['Volatility_50d'] * np.sqrt(252)
                df_volatility = df_volatility.dropna()
                
                if len(df_volatility) > 0:
                    fig_vol = go.Figure()
                    
                    fig_vol.add_trace(go.Scatter(
                        x=df_volatility['Data'],
                        y=df_volatility['Volatility_10d'],
                        name='Volatility 10d',
                        mode='lines',
                        line=dict(color='#e74c3c', width=2.5),
                        fill='tozeroy',
                        fillcolor='rgba(231, 76, 60, 0.2)'
                    ))
                    
                    fig_vol.add_trace(go.Scatter(
                        x=df_volatility['Data'],
                        y=df_volatility['Volatility_50d'],
                        name='Volatility 50d',
                        mode='lines',
                        line=dict(color='#3498db', width=2.5),
                        fill='tozeroy',
                        fillcolor='rgba(52, 152, 219, 0.2)'
                    ))
                    
                    fig_vol.update_layout(
                        xaxis=dict(title='Data', showgrid=True, gridcolor='#333333', color='white'),
                        yaxis=dict(title='Volatilità (%)', showgrid=True, gridcolor='#333333', ticksuffix='%', color='white'),
                        hovermode='x unified',
                        height=600,
                        plot_bgcolor='#0e1117',
                        paper_bgcolor='#0e1117',
                        font=dict(color='white')
                    )
                    
                    st.plotly_chart(fig_vol, use_container_width=True)
                    
                    col_vol1, col_vol2, col_vol3, col_vol4 = st.columns(4)
                    
                    with col_vol1:
                        st.metric("Vol 10d (annualizzata)", f"{df_volatility['Volatility_10d_annual'].iloc[-1]:.2f}%")
                    with col_vol2:
                        st.metric("Vol 50d (annualizzata)", f"{df_volatility['Volatility_50d_annual'].iloc[-1]:.2f}%")
                    with col_vol3:
                        st.metric("Media Vol 10d (ann.)", f"{df_volatility['Volatility_10d_annual'].mean():.2f}%")
                    with col_vol4:
                        st.metric("Media Vol 50d (ann.)", f"{df_volatility['Volatility_50d_annual'].mean():.2f}%")
            
            except Exception as e:
                st.warning(f"⚠️ Errore calcolo volatilità: {str(e)}")
        
        # ==================== METRICHE ====================
        if show_metrics and len(df_filtered) > 0:
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
    
    except Exception as e:
        st.error(f"❌ Errore: {str(e)}")
        with st.expander("🔍 Dettagli errore"):
            st.code(str(e))


if __name__ == "__main__":
    portfolio_tracker_app()
