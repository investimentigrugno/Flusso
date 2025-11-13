import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import requests

# ⭐ IMPORT dalla funzione esistente
from portfolio import load_sheet_csv

# Configurazione pagina
st.set_page_config(
    page_title="Gestione Ordini",
    page_icon="🕹️",
    layout="wide"
)

# ==================== CONFIGURAZIONE ====================
SPREADSHEET_ID_ORDINI = "1mD9jxDJv26aZwCdIbvQVjlJGBhRwKWwQnPpPPq0ON5Y"
GID_ORDINI = "1901209178"

SPREADSHEET_ID_PORTFOLIO = "1mD9jxDJv26aZwCdIbvQVjlJGBhRwKWwQnPpPPq0ON5Y"
GID_PORTFOLIO_STATUS = "1033121372"

WEBHOOK_URL_ORDINI = "https://script.google.com/macros/s/AKfycbx_lAUdZTKFgybEbjG_6RHTf08hnXtOlLfSaSxuP7RR5-HmEKiDpjwDpJKIAayXQSjLQw/exec"


def get_liquidita_disponibile():
    """Carica la liquidità disponibile dal foglio Portfolio"""
    try:
        df_liquidity = load_sheet_csv(SPREADSHEET_ID_PORTFOLIO, GID_PORTFOLIO_STATUS)
        df_liquidity = pd.DataFrame(
            df_liquidity.iloc[2:3, 0:4].values,
            columns=df_liquidity.iloc[1, 0:4].values
        )
        
        liquidita = df_liquidity.iloc[0, 2]  # Terza colonna
        
        if isinstance(liquidita, str):
            liquidita = float(liquidita.replace('€', '').replace('.', '').replace(',', '.').strip())
        
        return float(liquidita)
        
    except Exception as e:
        st.sidebar.error(f"Errore caricamento liquidità: {str(e)}")
        return 0.0


def aggiorna_stato_ordine_via_webhook(row_number, stato_esecuzione, webhook_url):
    """Aggiorna lo stato di un ordine"""
    try:
        payload = {
            "action": "update_stato_ordine",
            "row_number": row_number,
            "stato_esecuzione": stato_esecuzione,
            "data_esecuzione": datetime.now().strftime('%d/%m/%Y')
        }
        
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('success', False), result.get('message', 'Risposta sconosciuta')
        else:
            return False, f"Errore HTTP {response.status_code}"
            
    except Exception as e:
        return False, f"Errore: {str(e)}"


def calcola_valore_ordini_attivi(df_ordini):
    """Calcola il valore totale degli ordini attivi"""
    if df_ordini is None or df_ordini.empty:
        return 0.0
    
    ordini_attivi = df_ordini[df_ordini['STATO'] == 'Attivo'].copy()
    
    if 'N.AZIONI' in ordini_attivi.columns and 'ENTRY PRICE' in ordini_attivi.columns:
        ordini_attivi['VALORE'] = pd.to_numeric(ordini_attivi['N.AZIONI'], errors='coerce') * \
                                   pd.to_numeric(ordini_attivi['ENTRY PRICE'], errors='coerce')
        return ordini_attivi['VALORE'].sum()
    
    return 0.0


def ordini_app():
    """Applicazione Gestione Ordini"""
    
    st.title("🕹️ Gestione Ordini")
    st.markdown("Monitora e gestisci gli ordini di trading approvati")
    st.markdown("---")
    
    # ==================== SIDEBAR ====================
    st.sidebar.markdown("### ⚙️ Opzioni")
    
    if st.sidebar.button("🔄 Aggiorna Dati", type="primary"):
        st.cache_data.clear()
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.caption("💡 I dati vengono aggiornati automaticamente ogni 2 minuti")
    
    # ==================== CARICA DATI ====================
    try:
        # Carica liquidità
        with st.spinner("Caricamento dati Portfolio..."):
            liquidita_disponibile = get_liquidita_disponibile()
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 💰 Liquidità Portfolio")
        st.sidebar.metric("Disponibile", f"€ {liquidita_disponibile:,.2f}")
        
        # ⭐ CARICA ORDINI CON DEBUG
        with st.spinner("Caricamento ordini..."):
            df_ordini = load_sheet_csv(SPREADSHEET_ID_ORDINI, GID_ORDINI)
        
        # ⭐ DEBUG
        st.write("### 🔍 DEBUG Caricamento")
        st.write(f"Spreadsheet ID: {SPREADSHEET_ID_ORDINI}")
        st.write(f"GID: {GID_ORDINI}")
        
        if df_ordini is None:
            st.error("❌ df_ordini è None - Foglio non accessibile!")
            st.info("Verifica che il foglio sia pubblico: File → Condividi → Chiunque abbia il link")
            st.stop()
        
        st.write(f"✅ Caricato: {len(df_ordini)} righe, {len(df_ordini.columns)} colonne")
        st.write("**Colonne trovate:**")
        st.write(df_ordini.columns.tolist())
        st.write("**Prime 3 righe:**")
        st.dataframe(df_ordini.head(3))
        
        if df_ordini.empty:
            st.warning("⚠️ DataFrame vuoto")
            st.stop()
        
        # ⭐ DEFINISCI COLONNE CORRETTE (dal tuo foglio)
        expected_columns = [
            'DATA', 'TIME', 'COMPONENTE1', 'COMPONENTE2',
            'VOTO A FAVORE', 'STATO', 'ASSET', 'PROPOSTA',
            'ENTRY PRICE', 'N.AZIONI', '% SU TOT. PF.',
            'TP', 'SL', 'TEMPO'
        ]
        
        if len(df_ordini.columns) >= 14:
            df_ordini.columns = expected_columns[:len(df_ordini.columns)]
        
        df_ordini['ROW_NUMBER'] = range(2, len(df_ordini) + 2)
        
        # Converti date
        if 'DATA' in df_ordini.columns:
            df_ordini['DATA'] = pd.to_datetime(df_ordini['DATA'], format='%d/%m/%Y', errors='coerce', dayfirst=True)
        
        # Gestisci STATO
        if 'STATO' not in df_ordini.columns:
            st.error("❌ Colonna STATO non trovata!")
            st.stop()
        
        df_ordini['STATO'] = df_ordini['STATO'].fillna('Attivo')
        df_ordini['STATO'] = df_ordini['STATO'].replace('', 'Attivo')
        
        # Rimuovi righe vuote
        mask_valide = df_ordini[['ASSET', 'PROPOSTA']].notna().any(axis=1)
        df_ordini = df_ordini[mask_valide]
        
        df_ordini = df_ordini.sort_values('DATA', ascending=False, na_position='last').reset_index(drop=True)
        
        st.success(f"✅ {len(df_ordini)} ordini caricati correttamente!")
        st.markdown("---")
        
        # ==================== CALCOLA METRICHE ====================
        valore_ordini_attivi = calcola_valore_ordini_attivi(df_ordini)
        liquidita_effettiva = liquidita_disponibile - valore_ordini_attivi
        
        totali = len(df_ordini)
        attivi = len(df_ordini[df_ordini['STATO'] == 'Attivo'])
        eseguiti = len(df_ordini[df_ordini['STATO'] == 'Eseguito'])
        cancellati = len(df_ordini[df_ordini['STATO'] == 'Cancellato'])
        
        st.session_state.liquidita_disponibile = liquidita_disponibile
        st.session_state.valore_ordini_attivi = valore_ordini_attivi
        st.session_state.liquidita_effettiva = liquidita_effettiva
        
        # ==================== METRICHE ====================
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("💰 Liquidità Portfolio", f"€ {liquidita_disponibile:,.2f}")
        
        with col2:
            st.metric("📦 Valore Ordini Attivi", f"€ {valore_ordini_attivi:,.2f}", delta=f"{attivi} ordini")
        
        with col3:
            perc = (valore_ordini_attivi / liquidita_disponibile * 100) if liquidita_disponibile > 0 else 0
            st.metric("✅ Liquidità Effettiva", f"€ {liquidita_effettiva:,.2f}", delta=f"{perc:.1f}% impegnata", delta_color="inverse")
        
        with col4:
            st.metric("📊 Totale Ordini", totali, delta=f"✅ {eseguiti} | ❌ {cancellati}")
        
        st.markdown("---")
        
        # ==================== ORDINI ATTIVI ====================
        st.markdown("## 🔥 Ordini Attivi")
        
        ordini_attivi = df_ordini[df_ordini['STATO'] == 'Attivo'].copy()
        
        if ordini_attivi.empty:
            st.success("✅ Nessun ordine attivo")
        else:
            st.info(f"📋 **{len(ordini_attivi)} ordini** in attesa")
            
            for idx, ordine in ordini_attivi.iterrows():
                with st.container():
                    col_h, col_b = st.columns([3, 1])
                    
                    with col_h:
                        st.markdown(f"### {ordine.get('ASSET', 'N/A')} - {ordine.get('PROPOSTA', 'N/A')}")
                    
                    with col_b:
                        st.warning("⏳ ATTIVO")
                    
                    col1, col2, col3 = st.columns([1, 1, 2])
                    
                    with col1:
                        if st.button("✅ Eseguito", key=f"esegui_{ordine['ROW_NUMBER']}", use_container_width=True, type="primary"):
                            success, msg = aggiorna_stato_ordine_via_webhook(ordine['ROW_NUMBER'], 'Eseguito', WEBHOOK_URL_ORDINI)
                            if success:
                                st.success(msg)
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(msg)
                    
                    with col2:
                        if st.button("❌ Cancella", key=f"canc_{ordine['ROW_NUMBER']}", use_container_width=True):
                            success, msg = aggiorna_stato_ordine_via_webhook(ordine['ROW_NUMBER'], 'Cancellato', WEBHOOK_URL_ORDINI)
                            if success:
                                st.success(msg)
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(msg)
                    
                    st.markdown("---")
        
        # ==================== ORDINI ESEGUITI ====================
        st.markdown("## ✅ Ordini Eseguiti")
        
        ordini_eseguiti = df_ordini[df_ordini['STATO'] == 'Eseguito'].copy()
        
        if not ordini_eseguiti.empty:
            st.success(f"📊 {len(ordini_eseguiti)} completati")
            st.dataframe(ordini_eseguiti[['DATA', 'ASSET', 'PROPOSTA', 'ENTRY PRICE', 'N.AZIONI']], use_container_width=True, hide_index=True)
        else:
            st.info("Nessun ordine eseguito")
        
        # ==================== ORDINI CANCELLATI ====================
        st.markdown("## ❌ Ordini Cancellati")
        
        ordini_cancellati = df_ordini[df_ordini['STATO'] == 'Cancellato'].copy()
        
        if not ordini_cancellati.empty:
            with st.expander(f"Mostra {len(ordini_cancellati)} cancellati"):
                st.dataframe(ordini_cancellati[['DATA', 'ASSET', 'PROPOSTA']], use_container_width=True, hide_index=True)
        else:
            st.info("Nessun ordine cancellato")
    
    except Exception as e:
        st.error(f"❌ Errore: {str(e)}")
        import traceback
        st.code(traceback.format_exc())


if __name__ == "__main__":
    ordini_app()
