import streamlit as st
import pandas as pd


def portfolio_tracker_app():
    """Applicazione Portfolio Tracker"""
    
    st.title("📊 Portfolio Tracker")
    st.markdown("---")
    
    # URL del foglio Google Sheets
    sheet_url = "https://docs.google.com/spreadsheets/d/1mD9jxDJv26aZwCdIbvQVjlJGBhRwKWwQnPpPPq0ON5Y/edit"
    csv_url = sheet_url.replace('/edit', '/export?format=csv&gid=0')
    
    # Opzioni nella sidebar
    st.sidebar.markdown("### ⚙️ Opzioni Portfolio")
    show_metrics = st.sidebar.checkbox("Mostra metriche", value=True)
    
    try:
        with st.spinner("Caricamento dati dal Google Sheet..."):
            df = pd.read_csv(csv_url)
            
            # Tabella principale (prime 16 righe e 13 colonne)
            df_filtered = df.iloc[:16, :13]
            
           # Prendi righe 19-21 (inclusi) saltando la vuota (riga 18 vuota)
            df_summary = df.iloc[20, 3:12].copy()  # righe 20 e 21 nel foglio, quindi indici 19 e 20 in python
            
            header_names = ["DEPOSIT", "VALUE €", "P&L %", "P&L TOT", "P&L %", "P&L LIVE", "TOT $", "EUR/USD", "TOT €"]
            df_summary.columns = header_names

        st.success("✅ Dati caricati con successo!")
        
        # Visualizza tabella riepilogativa principale
        st.markdown("---")
        st.subheader("💼 Dati Principali del Portafoglio")
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
        
        # Visualizza tabella principale
        st.subheader("Portfolio Completo")
        st.dataframe(df_filtered, use_container_width=True, height=600, hide_index=True)
        
        # Print tabella principale in console
        print("\n" + "="*100)
        print("TABELLA PORTFOLIO COMPLETA")
        print("="*100)
        print(df_filtered.to_string())
        print("\n" + "="*100)
        
        # Print dati principali portafoglio in console
        print("\n" + "="*100)
        print("DATI PRINCIPALI PORTAFOGLIO")
        print("="*100)
        print(df_summary.to_string())
        print("\n" + "="*100)

        
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
            
            # Distribuzione per asset
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
                    if position:  # Ignora valori vuoti
                        st.write(f"• {position}: {count}")
        
        
    except Exception as e:
        st.error(f"❌ Errore nel caricamento dei dati: {str(e)}")
        st.info("💡 Verifica che il foglio Google Sheets sia pubblicamente accessibile.")
        
        # Mostra dettagli errore in expander
        with st.expander("🔍 Dettagli errore"):
            st.code(str(e))
