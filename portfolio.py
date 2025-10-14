import streamlit as st
import pandas as pd


def portfolio_tracker_app():
    """Applicazione Portfolio Tracker"""
    
    st.title("📊 Portfolio Tracker")
    st.markdown("---")
    
    sheet_url = "https://docs.google.com/spreadsheets/d/1mD9jxDJv26aZwCdIbvQVjlJGBhRwKWwQnPpPPq0ON5Y/edit"
    csv_url = sheet_url.replace('/edit', '/export?format=csv&gid=0')
    
    st.sidebar.markdown("### ⚙️ Opzioni Portfolio")
    show_metrics = st.sidebar.checkbox("Mostra metriche", value=True)
    
    try:
        with st.spinner("Caricamento dati dal Google Sheet..."):
            df = pd.read_csv(csv_url)
            
            # Tabella principale (prime 16 righe e 13 colonne)
            df_filtered = df.iloc[:16, :13]
            
            # Tabella dati principali forzando manualmente intestazioni
            df_summary = df.iloc[19:20, 3:12].copy()  # Prendo soltanto la riga dati (es. riga 20)
            
            # Definisci manualmente i nomi delle colonne:
            forced_headers = [
                "DEPOSIT", "VALUE €", "P&L %", "P&L TOT", "P&L %_2", 
                "P&L LIVE", "TOT $", "EUR/USD", "TOT €"
            ]
            
            df_summary.columns = forced_headers
            
            # Reset indice per pulizia tabella
            df_summary = df_summary.reset_index(drop=True)
        
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
        
        if show_metrics:
            st.markdown("---")
            st.subheader("📊 Statistiche Portfolio")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(label="Totale Asset", value=len(df_filtered))
            
            with col2:
                asset_types = df_filtered['ASSET'].value_counts()
                st.metric(label="Categorie Asset", value=len(asset_types))
            
            with col3:
                st.metric(label="Righe", value=df_filtered.shape[0])
            
            with col4:
                st.metric(label="Colonne", value=df_filtered.shape[1])
            
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
        st.info("💡 Verifica che il foglio Google Sheets sia pubblicamente accessibile.")
        
        with st.expander("🔍 Dettagli errore"):
            st.code(str(e))
