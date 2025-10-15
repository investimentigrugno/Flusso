import streamlit as st
import pandas as pd


def portfolio_tracker_app():
    """Applicazione Portfolio Tracker"""
    
    st.title("📊 Portfolio Tracker")
    st.markdown("---")
    
    sheet_url = "https://docs.google.com/spreadsheets/d/1mD9jxDJv26aZwCdIbvQVjlJGBhRwKWwQnPpPPq0ON5Y/edit"
    csv_url = sheet_url.replace('/edit', '/export?format=csv&gid=0')
    
    # Opzioni nella sidebar
    st.sidebar.markdown("### ⚙️ Opzioni Portfolio")
    show_metrics = st.sidebar.checkbox("Mostra metriche", value=False)
    
    
    try:
        with st.spinner("Caricamento dati dal Google Sheet..."):
            df = pd.read_csv(csv_url)
            
            # Tabella principale (prime 16 righe e 13 colonne)
            df_filtered = df.iloc[:16, :13]
            
            # Tabella dati principali forzando manualmente intestazioni
            df_summary = df.iloc[18:19, 3:12].copy()  # Prendo soltanto la riga dati (es. riga 20)
            
            # Definisci manualmente i nomi delle colonne:
            summary_headers = [
                "DEPOSIT", "VALUE €", "P&L %", "P&L TOT", "P&L % LIVE", 
                "P&L LIVE", "TOT $", "EUR/USD", "TOT €"]
            
            df_summary.columns = summary_headers
                    
        st.success("✅ Dati caricati con successo!")
        
        st.markdown("---")
        st.subheader("💼 Dati Principali del Portafoglio")
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
        
        st.subheader("Portfolio Completo")
        st.dataframe(df_filtered, use_container_width=True, height=600, hide_index=True)
        
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
        
        st.markdown("---")
        st.subheader("Distribuzione Valore Portfolio")
            
        # Prepara i dati per il grafico a torta
        # Rimuovi il simbolo € e converti in float
        df_chart = df_filtered[['NAME', 'VALUE']].copy()
        
        # Pulisci la colonna VALUE rimuovendo € e sostituendo virgola con punto
        df_chart['VALUE_CLEAN'] = df_chart['VALUE'].str.replace('€', '').str.replace('.', '').str.replace(',', '.').str.strip()
        
        # Converti in numerico
        df_chart['VALUE_NUMERIC'] = pd.to_numeric(df_chart['VALUE_CLEAN'], errors='coerce')
        
        # Rimuovi righe con valori NaN o negativi
        df_chart = df_chart[df_chart['VALUE_NUMERIC'] > 0].dropna()
        
        # Crea il grafico a torta
        import plotly.express as px
        
        fig = px.pie(
            df_chart, 
            values='VALUE_NUMERIC', 
            names='NAME',
            title='Distribuzione del Valore per Asset',
            hole=0.3,  # Crea un donut chart (opzionale, rimuovi per torta piena)
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

        # Grafico a torta Distribuzione per Tipo di Asset
        st.markdown("---")
        st.subheader("💰 Distribuzione Valore per Tipo di Asset")
        
        # Prepara dati per tipo di asset
        df_asset_type = df_filtered[['ASSET', 'VALUE']].copy()
        df_asset_type = df_asset_type[df_asset_type['ASSET'].notna() & (df_asset_type['ASSET'] != '')]
        
        # Pulisci valori
        df_asset_type['VALUE_CLEAN'] = df_asset_type['VALUE'].str.replace('€', '').str.replace('.', '').str.replace(',', '.').str.strip()
        df_asset_type['VALUE_NUMERIC'] = pd.to_numeric(df_asset_type['VALUE_CLEAN'], errors='coerce')
        df_asset_type = df_asset_type[df_asset_type['VALUE_NUMERIC'] > 0].dropna()
        
        # Aggrega per tipo di asset
        asset_type_agg = df_asset_type.groupby('ASSET')['VALUE_NUMERIC'].sum().reset_index()
        asset_type_agg.columns = ['Tipo Asset', 'Valore']
        
        # Ordina per valore decrescente
        asset_type_agg = asset_type_agg.sort_values('Valore', ascending=False)
        
        import plotly.express as px
        
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


        # Grafico a torta Distribuzione Posizioni (L/B/P)
        st.markdown("---")
        st.subheader("Distribuzione Valore per Tipo di Posizione")
        
        # Grafico per valore posizioni
        df_pos_value = df_filtered[['LUNGO/BREVE', 'VALUE']].copy()
        df_pos_value = df_pos_value[df_pos_value['LUNGO/BREVE'].notna() & (df_pos_value['LUNGO/BREVE'] != '')]
        
        # Pulisci valori
        df_pos_value['VALUE_CLEAN'] = df_pos_value['VALUE'].str.replace('€', '').str.replace('.', '').str.replace(',', '.').str.strip()
        df_pos_value['VALUE_NUMERIC'] = pd.to_numeric(df_pos_value['VALUE_CLEAN'], errors='coerce')
        df_pos_value = df_pos_value[df_pos_value['VALUE_NUMERIC'] > 0].dropna()
        
        # Aggrega per posizione
        pos_value_agg = df_pos_value.groupby('LUNGO/BREVE')['VALUE_NUMERIC'].sum().reset_index()
        pos_value_agg.columns = ['Posizione', 'Valore']
        
        # Mappa nomi completi
        position_map = {
            'L': 'Lungo',
            'B': 'Breve', 
            'P': 'Passività'
        }
        pos_value_agg['Posizione'] = pos_value_agg['Posizione'].map(position_map)
        
        import plotly.express as px
        
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
        
        # Grafico combinato P&L nel tempo con dati dal foglio "dati"
        st.markdown("---")
        st.subheader("📈 Andamento P&L nel Tempo")
        
        # Carica il foglio "dati"
        csv_url_dati = sheet_url.replace('/edit', '/export?format=csv&gid=1009022145')
        
        try:
            df_dati = pd.read_csv(csv_url_dati)
            
            # Estrai le colonne necessarie (colonna 10=DATA, 3=P&L%, 12=SMA9%, 13=SMA20%)
            # Python usa indice 0-based: col 10=indice 9, col 3=indice 2, col 12=indice 11, col 13=indice 12
            df_chart_data = df_dati.iloc[:, [9, 2, 11, 12]].copy()
            
            # Rinomina le colonne
            df_chart_data.columns = ['Data', 'P&L%', 'SMA9%', 'SMA20%']
            
            # Converti la colonna Data in formato datetime
            df_chart_data['Data'] = pd.to_datetime(df_chart_data['Data'], errors='coerce')
            
            # Rimuovi righe con date invalide
            df_chart_data = df_chart_data.dropna(subset=['Data'])
            
            # Filtra solo dati dal 2025 in poi
            df_chart_data = df_chart_data[df_chart_data['Data'] >= '2025-01-01']
            
            # Funzione per pulire e convertire percentuali
            def clean_percentage(col):
                if col.dtype == 'object':
                    # Rimuovi simbolo % e converti virgola in punto
                    col = col.str.replace('%', '').str.replace(',', '.').str.strip()
                return pd.to_numeric(col, errors='coerce')
            
            # Pulisci e converti le colonne percentuali
            df_chart_data['P&L%'] = clean_percentage(df_chart_data['P&L%'])
            df_chart_data['SMA9%'] = clean_percentage(df_chart_data['SMA9%'])
            df_chart_data['SMA20%'] = clean_percentage(df_chart_data['SMA20%'])
            
            # Rimuovi righe con valori NaN
            df_chart_data = df_chart_data.dropna()
            
            # Ordina per data
            df_chart_data = df_chart_data.sort_values('Data')
            
            # Verifica che ci siano dati disponibili
            if len(df_chart_data) == 0:
                st.warning("⚠️ Nessun dato disponibile per il 2025.")
            else:
                # Crea il grafico combinato con Plotly
                import plotly.graph_objects as go
                
                fig_combined = go.Figure()
                
                # Aggiungi le barre per P&L%
                fig_combined.add_trace(go.Bar(
                    x=df_chart_data['Data'],
                    y=df_chart_data['P&L%'],
                    name='P&L %',
                    marker_color='#3498db',
                    yaxis='y',
                    hovertemplate='<b>Data:</b> %{x|%d/%m/%Y}<br><b>P&L:</b> %{y:.2f}%<extra></extra>'
                ))
                
                # Aggiungi la prima linea (SMA9%)
                fig_combined.add_trace(go.Scatter(
                    x=df_chart_data['Data'],
                    y=df_chart_data['SMA9%'],
                    name='SMA9 %',
                    mode='lines+markers',
                    line=dict(color='#e74c3c', width=2),
                    marker=dict(size=4),
                    yaxis='y',
                    hovertemplate='<b>Data:</b> %{x|%d/%m/%Y}<br><b>SMA9:</b> %{y:.2f}%<extra></extra>'
                ))
                
                # Aggiungi la seconda linea (SMA20%)
                fig_combined.add_trace(go.Scatter(
                    x=df_chart_data['Data'],
                    y=df_chart_data['SMA20%'],
                    name='SMA20 %',
                    mode='lines+markers',
                    line=dict(color='#2ecc71', width=2),
                    marker=dict(size=4),
                    yaxis='y',
                    hovertemplate='<b>Data:</b> %{x|%d/%m/%Y}<br><b>SMA20:</b> %{y:.2f}%<extra></extra>'
                ))
                
                # Aggiungi una linea orizzontale allo 0% per riferimento
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
                
                # Statistiche rapide sotto il grafico
                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                
                with col_stat1:
                    ultimo_pl = df_chart_data['P&L%'].iloc[-1]
                    st.metric(
                        label="Ultimo P&L %",
                        value=f"{ultimo_pl:.2f}%"
                    )
                
                with col_stat2:
                    media_pl = df_chart_data['P&L%'].mean()
                    st.metric(
                        label="Media P&L %",
                        value=f"{media_pl:.2f}%"
                    )
                
                with col_stat3:
                    max_pl = df_chart_data['P&L%'].max()
                    st.metric(
                        label="Max P&L %",
                        value=f"{max_pl:.2f}%"
                    )
                
                with col_stat4:
                    min_pl = df_chart_data['P&L%'].min()
                    st.metric(
                        label="Min P&L %",
                        value=f"{min_pl:.2f}%"
                    )
            
        except Exception as e:
            st.warning(f"⚠️ Impossibile caricare i dati dal foglio 'dati': {str(e)}")
            st.info("💡 Verifica che il foglio 'dati' esista e che il gid sia corretto nell'URL.")
            with st.expander("🔍 Dettagli errore"):
                st.code(str(e))

        # Grafico Volatilità a Breve e Lungo Termine
        st.markdown("---")
        st.subheader("📉 Volatilità del Portfolio")
        
        # Usa lo stesso foglio "dati" già caricato
        csv_url_volatilita = sheet_url.replace('/edit', '/export?format=csv&gid=1009022145')
        
        try:
            df_volatilita = pd.read_csv(csv_url_volatilita)
            
            # Estrai le colonne necessarie (colonna 3=DATA, 14=Volatilità breve, 15=Volatilità lungo)
            # Python usa indice 0-based: col 3=indice 2, col 14=indice 13, col 15=indice 14
            df_vol_data = df_volatilita.iloc[:, [2, 13, 14]].copy()
            
            # Rinomina le colonne
            df_vol_data.columns = ['Data', 'Volatilità Breve', 'Volatilità Lungo']
            
            # Converti la colonna Data in formato datetime
            df_vol_data['Data'] = pd.to_datetime(df_vol_data['Data'], errors='coerce')
            
            # Rimuovi righe con date invalide
            df_vol_data = df_vol_data.dropna(subset=['Data'])
            
            # Filtra solo dati dal 2025 in poi
            df_vol_data = df_vol_data[df_vol_data['Data'] >= '2025-01-01']
            
            # Funzione per pulire e convertire percentuali
            def clean_percentage(col):
                if col.dtype == 'object':
                    # Rimuovi simbolo % e converti virgola in punto
                    col = col.str.replace('%', '').str.replace(',', '.').str.strip()
                return pd.to_numeric(col, errors='coerce')
            
            # Pulisci e converti le colonne percentuali
            df_vol_data['Volatilità Breve'] = clean_percentage(df_vol_data['Volatilità Breve'])
            df_vol_data['Volatilità Lungo'] = clean_percentage(df_vol_data['Volatilità Lungo'])
            
            # Rimuovi righe con valori NaN
            df_vol_data = df_vol_data.dropna()
            
            # Ordina per data
            df_vol_data = df_vol_data.sort_values('Data')
            
            # Verifica che ci siano dati disponibili
            if len(df_vol_data) == 0:
                st.warning("⚠️ Nessun dato di volatilità disponibile per il 2025.")
            else:
                # Crea il grafico con Plotly
                import plotly.graph_objects as go
                
                fig_volatility = go.Figure()
                
                # Aggiungi linea Volatilità Breve
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
                
                # Aggiungi linea Volatilità Lungo
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
                
                # Layout del grafico
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
                
                # Statistiche volatilità sotto il grafico
                col_vol1, col_vol2, col_vol3, col_vol4 = st.columns(4)
                
                with col_vol1:
                    ultima_vol_breve = df_vol_data['Volatilità Breve'].iloc[-1]
                    st.metric(
                        label="Ultima Vol. Breve",
                        value=f"{ultima_vol_breve:.2f}%"
                    )
                
                with col_vol2:
                    ultima_vol_lungo = df_vol_data['Volatilità Lungo'].iloc[-1]
                    st.metric(
                        label="Ultima Vol. Lungo",
                        value=f"{ultima_vol_lungo:.2f}%"
                    )
                
                with col_vol3:
                    media_vol_breve = df_vol_data['Volatilità Breve'].mean()
                    st.metric(
                        label="Media Vol. Breve",
                        value=f"{media_vol_breve:.2f}%"
                    )
                
                with col_vol4:
                    media_vol_lungo = df_vol_data['Volatilità Lungo'].mean()
                    st.metric(
                        label="Media Vol. Lungo",
                        value=f"{media_vol_lungo:.2f}%"
                    )
            
        except Exception as e:
            st.warning(f"⚠️ Impossibile caricare i dati di volatilità: {str(e)}")
            st.info("💡 Verifica che le colonne di volatilità esistano nel foglio 'dati'.")
            with st.expander("🔍 Dettagli errore"):
                st.code(str(e))



            # Metriche
        if show_metrics:
            st.markdown("---")
            st.subheader("📊 Statistiche Portfolio")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    label="Totale Asset",
                    value=len(df_filtered),
                    delta=None
                )
            
            with col2:
                # Conta asset per tipo
                asset_types = df_filtered['ASSET'].value_counts()
                st.metric(
                    label="Categorie Asset",
                    value=len(asset_types),
                    delta=None
                )
            
            with col3:
                st.metric(
                    label="Righe",
                    value=df_filtered.shape[0],
                    delta=None
                )
            
            with col4:
                st.metric(
                    label="Colonne",
                    value=df_filtered.shape[1],
                    delta=None
                )
            
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
                            st.write(f"• {position}: {count}")           # Grafico a torta Portfolio
                
                
    except Exception as e:
        st.error(f"❌ Errore nel caricamento dei dati: {str(e)}")
        st.info("💡 Verifica che il foglio Google Sheets sia pubblicamente accessibile.")
        
        with st.expander("🔍 Dettagli errore"):
            st.code(str(e))
