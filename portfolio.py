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
