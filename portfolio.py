import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import time


@st.cache_data(ttl=120)
@st.cache_data(ttl=120)
def load_sheet_csv(spreadsheet_id, gid):
    """Carica foglio pubblico via CSV export e rimuove righe vuote"""
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # ⭐ HEADER=0 è il default (usa prima riga come intestazioni) ⭐
            df = pd.read_csv(url, header=0)
            
            if not df.empty:
                # ⭐ RIMUOVI IMMEDIATAMENTE ULTIMA RIGA SE VUOTA ⭐
                # Questo risolve il problema della riga vuota finale nel CSV di Google
                while len(df) > 0:
                    ultima_riga = df.iloc[-1]
                    
                    # Controlla se TUTTI i valori nell'ultima riga sono NaN o stringa vuota
                    is_empty = all(
                        pd.isna(val) or (isinstance(val, str) and val.strip() == '')
                        for val in ultima_riga
                    )
                    
                    if is_empty:
                        # Ultima riga vuota, eliminala
                        df = df.iloc[:-1]
                    else:
                        # Ultima riga valida, esci dal loop
                        break
                
                # ⭐ PULIZIA AGGIUNTIVA: Rimuovi tutte le righe completamente vuote ⭐
                df = df.dropna(how='all')
                
                # Reset index finale
                df = df.reset_index(drop=True)
                
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
    show_debug = st.sidebar.checkbox("🔍 Debug: Info caricamento", value=False)
    
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
        
        # ==================== FILTRAGGIO BASATO SOLO SU TICKER ====================
        df_original_len = len(df)
        
        # ⭐ FILTRO UNICO: Mantieni solo righe con TICKER valido (colonna C, indice 2) ⭐
        df_filtered = df.copy()
        
        # Step 1: Rimuovi righe completamente vuote
        df_filtered = df_filtered.dropna(how='all')
        
        # Step 2: Rimuovi righe dove tutte le celle sono stringhe vuote
        mask_non_vuote = df_filtered.apply(
            lambda row: any(pd.notna(val) and str(val).strip() != '' for val in row), 
            axis=1
        )
        df_filtered = df_filtered[mask_non_vuote]
        
        # Step 3: FILTRO PRINCIPALE - Mantieni solo righe con TICKER valido
        if len(df_filtered.columns) >= 3:
            ticker_col = df_filtered.iloc[:, 2]  # Colonna C (TICKER)
            
            # Ticker deve essere non-nullo e non-vuoto
            mask_ticker = ticker_col.notna() & (ticker_col.astype(str).str.strip() != '')
            df_filtered = df_filtered[mask_ticker]
        
        # Step 4: Reset index
        df_filtered = df_filtered.reset_index(drop=True)
        
        # Step 5: Controllo finale - Rimuovi ultima riga se ancora vuota (loop sicuro)
        while len(df_filtered) > 0:
            ultima_riga = df_filtered.iloc[-1]
            
            # Controlla se il ticker dell'ultima riga è vuoto
            ticker_ultima = str(ultima_riga.iloc[2] if len(ultima_riga) > 2 else '').strip()
            
            if ticker_ultima == '' or pd.isna(ultima_riga.iloc[2] if len(ultima_riga) > 2 else None):
                # Ultima riga senza ticker, rimuovila
                df_filtered = df_filtered.iloc[:-1]
                df_filtered = df_filtered.reset_index(drop=True)
            else:
                # Ultima riga con ticker valido, esci
                break
        
        removed_total = df_original_len - len(df_filtered)
        
        # Carica Portfolio Status
        df_summary = df_status.iloc[0:1, :].copy().reset_index(drop=True)
        
        st.success(f"✅ Dati caricati con successo! ({len(df_filtered)} posizioni in portfolio)")
        
        # Debug info
        if show_debug:
            with st.expander("🔍 Info Caricamento"):
                st.write(f"• Righe totali caricate: {df_original_len}")
                st.write(f"• Righe filtrate (vuote): {removed_total}")
                st.write(f"• **Righe finali valide: {len(df_filtered)}**")
                st.write(f"• Colonne: {df_filtered.shape[1]}")
        
        # ==================== SEZIONE TABELLE ====================
        st.markdown("---")
        st.subheader("💼 Portfolio Status")
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.subheader("📋 Portfolio Completo")
        st.caption(f"📊 {len(df_filtered)} strumenti in portafoglio")
        
        if len(df_filtered) > 0:
            st.dataframe(df_filtered, use_container_width=True, hide_index=True)
        else:
            st.info("📭 Nessuna posizione nel portfolio")
        
        # ==================== GRAFICO 1: DISTRIBUZIONE VALORE ====================
        if len(df_filtered) > 0:
            st.markdown("---")
            st.subheader("📊 Distribuzione Valore Portfolio")
            
            # Verifica che esistano le colonne NAME e VALUE
            if len(df_filtered.columns) >= 9:  # Colonna I (VALUE) è indice 8
                df_chart = df_filtered.iloc[:, [3, 8]].copy()  # NAME (D) e VALUE (I)
                df_chart.columns = ['NAME', 'VALUE']
                
                # Converti VALUE in numerico
                df_chart['VALUE_CLEAN'] = df_chart['VALUE'].astype(str).str.replace('€', '').str.replace('.', '').str.replace(',', '.').str.strip()
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
                
                if len(df_filtered.columns) >= 9:
                    df_asset_type = df_filtered.iloc[:, [1, 8]].copy()  # ASSET (B) e VALUE (I)
                    df_asset_type.columns = ['ASSET', 'VALUE']
                    df_asset_type = df_asset_type[df_asset_type['ASSET'].notna() & (df_asset_type['ASSET'].astype(str).str.strip() != '')]
                    
                    df_asset_type['VALUE_CLEAN'] = df_asset_type['VALUE'].astype(str).str.replace('€', '').str.replace('.', '').str.replace(',', '.').str.strip()
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
                
                if len(df_filtered.columns) >= 9:
                    df_pos_value = df_filtered.iloc[:, [0, 8]].copy()  # LUNGO/BREVE (A) e VALUE (I)
                    df_pos_value.columns = ['LUNGO/BREVE', 'VALUE']
                    df_pos_value = df_pos_value[df_pos_value['LUNGO/BREVE'].notna() & (df_pos_value['LUNGO/BREVE'].astype(str).str.strip() != '')]
                    
                    df_pos_value['VALUE_CLEAN'] = df_pos_value['VALUE'].astype(str).str.replace('€', '').str.replace('.', '').str.replace(',', '.').str.strip()
                    df_pos_value['VALUE_NUMERIC'] = pd.to_numeric(df_pos_value['VALUE_CLEAN'], errors='coerce')
                    df_pos_value = df_pos_value[df_pos_value['VALUE_NUMERIC'] > 0].dropna()
                    
                    if len(df_pos_value) > 0:
                        pos_value_agg = df_pos_value.groupby('LUNGO/BREVE')['VALUE_NUMERIC'].sum().reset_index()
                        pos_value_agg.columns = ['Posizione', 'Valore']
                        
                        position_map = {'L': 'LUNGO', 'B': 'BREVE', 'P': 'PASSIVITA'}
                        pos_value_agg['Posizione'] = pos_value_agg['Posizione'].map(position_map).fillna(pos_value_agg['Posizione'])
                        
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
                    df_chart_data['P&L%'] = df_chart_data['P&L%'].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
                
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
        if df_dati is not None and not df_dati.empty and len(df_chart_data) > 0:
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
                        fillcolor='rgba(231, 76, 60, 0.2)',
                        hovertemplate='<b>Data:</b> %{x|%d/%m/%Y}<br><b>Vol 10d:</b> %{y:.2f}%<extra></extra>'
                    ))
                    
                    fig_vol.add_trace(go.Scatter(
                        x=df_volatility['Data'],
                        y=df_volatility['Volatility_50d'],
                        name='Volatility 50d',
                        mode='lines',
                        line=dict(color='#3498db', width=2.5),
                        fill='tozeroy',
                        fillcolor='rgba(52, 152, 219, 0.2)',
                        hovertemplate='<b>Data:</b> %{x|%d/%m/%Y}<br><b>Vol 50d:</b> %{y:.2f}%<extra></extra>'
                    ))
                    
                    fig_vol.update_layout(
                        xaxis=dict(title='Data', showgrid=True, gridcolor='#333333', color='white'),
                        yaxis=dict(title='Volatilità (%)', showgrid=True, gridcolor='#333333', ticksuffix='%', color='white'),
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
                st.metric("Totale Posizioni", len(df_filtered))
            with col2:
                if len(df_filtered.columns) >= 2:
                    n_asset_types = df_filtered.iloc[:, 1].nunique()
                    st.metric("Categorie Asset", n_asset_types)
            with col3:
                st.metric("Righe", df_filtered.shape[0])
            with col4:
                st.metric("Colonne", df_filtered.shape[1])
    
    except Exception as e:
        st.error(f"❌ Errore: {str(e)}")
        with st.expander("🔍 Dettagli errore"):
            import traceback
            st.code(traceback.format_exc())


if __name__ == "__main__":
    portfolio_tracker_app()
