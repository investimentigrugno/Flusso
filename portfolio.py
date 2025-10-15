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
        
        # Carica il foglio "dati" (gid diverso dal foglio principale)
        # Devi trovare il gid del foglio "dati" nell'URL di Google Sheets
        # Per ora proviamo con gid=1, se non funziona dovrai verificare il gid corretto
        csv_url_dati = sheet_url.replace('/edit', '/export?format=csv&gid=1')
        
        try:
            df_dati = pd.read_csv(csv_url_dati)
            
            # Estrai le colonne necessarie (colonna 10=DATA, 3=P&L, 12 e 13)
            # Nota: Python usa indice 0-based, quindi col 10=indice 9, col 3=indice 2, col 12=indice 11, col 13=indice 12
            df_chart_data = df_dati.iloc[:, [9, 2, 11, 12]].copy()
            
            # Rinomina le colonne per chiarezza
            df_chart_data.columns = ['Data', 'P&L', 'Linea_1', 'Linea_2']
            
            # Converti la colonna Data in formato datetime
            df_chart_data['Data'] = pd.to_datetime(df_chart_data['Data'], errors='coerce')
            
            # Rimuovi righe con date invalide
            df_chart_data = df_chart_data.dropna(subset=['Data'])
            
            # Converti P&L e le altre colonne in numerico
            df_chart_data['P&L'] = pd.to_numeric(df_chart_data['P&L'], errors='coerce')
            df_chart_data['Linea_1'] = pd.to_numeric(df_chart_data['Linea_1'], errors='coerce')
            df_chart_data['Linea_2'] = pd.to_numeric(df_chart_data['Linea_2'], errors='coerce')
            
            # Ordina per data
            df_chart_data = df_chart_data.sort_values('Data')
            
            # Crea il grafico combinato con Plotly
            import plotly.graph_objects as go
            
            fig_combined = go.Figure()
            
            # Aggiungi le barre per P&L
            fig_combined.add_trace(go.Bar(
                x=df_chart_data['Data'],
                y=df_chart_data['P&L'],
                name='P&L',
                marker_color='#3498db',
                yaxis='y',
                hovertemplate='<b>Data:</b> %{x|%d/%m/%Y}<br><b>P&L:</b> €%{y:,.2f}<extra></extra>'
            ))
            
            # Aggiungi la prima linea (colonna 12)
            fig_combined.add_trace(go.Scatter(
                x=df_chart_data['Data'],
                y=df_chart_data['Linea_1'],
                name='Linea 1',
                mode='lines+markers',
                line=dict(color='#e74c3c', width=2),
                marker=dict(size=6),
                yaxis='y',
                hovertemplate='<b>Data:</b> %{x|%d/%m/%Y}<br><b>Valore:</b> %{y:,.2f}<extra></extra>'
            ))
            
            # Aggiungi la seconda linea (colonna 13)
            fig_combined.add_trace(go.Scatter(
                x=df_chart_data['Data'],
                y=df_chart_data['Linea_2'],
                name='Linea 2',
                mode='lines+markers',
                line=dict(color='#2ecc71', width=2),
                marker=dict(size=6),
                yaxis='y',
                hovertemplate='<b>Data:</b> %{x|%d/%m/%Y}<br><b>Valore:</b> %{y:,.2f}<extra></extra>'
            ))
            
            # Layout del grafico
            fig_combined.update_layout(
                title='Andamento P&L e Metriche nel Tempo',
                xaxis=dict(
                    title='Data',
                    showgrid=True,
                    gridcolor='lightgray'
                ),
                yaxis=dict(
                    title='Valore (€)',
                    showgrid=True,
                    gridcolor='lightgray'
                ),
                hovermode='x unified',
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                height=600,
                plot_bgcolor='white'
            )
            
            st.plotly_chart(fig_combined, use_container_width=True)
            
        except Exception as e:
            st.warning(f"⚠️ Impossibile caricare i dati dal foglio 'dati': {str(e)}")
            st.info("💡 Verifica che il foglio 'dati' esista e che il gid sia corretto nell'URL.")

        
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
