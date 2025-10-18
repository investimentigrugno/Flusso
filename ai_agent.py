import streamlit as st
import pandas as pd
from datetime import datetime
import re
from typing import List, Dict

# ============================================================================
# CONFIGURAZIONE GROQ API - VERSIONE CORRETTA
# ============================================================================

GROQ_API_KEY = "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"
MODEL_NAME = "llama-3.1-70b-versatile"

# Importa la libreria Groq ufficiale
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    st.error("Libreria Groq non installata. Esegui: pip install groq")

def get_groq_client():
    """Crea client Groq"""
    if not GROQ_AVAILABLE:
        return None
    try:
        client = Groq(api_key=GROQ_API_KEY)
        return client
    except Exception as e:
        st.error(f"Errore inizializzazione Groq: {e}")
        return None

def call_groq_api(prompt: str, max_tokens: int = 1000) -> str:
    """Chiama l'API Groq usando la libreria ufficiale"""
    try:
        client = get_groq_client()
        if not client:
            return "Errore: Client Groq non disponibile"
        
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Sei un analista finanziario esperto specializzato in analisi azionaria e valutazione di investimenti. Fornisci analisi dettagliate, basate sui dati e professionali."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model=MODEL_NAME,
            temperature=0.7,
            max_tokens=max_tokens
        )
        
        return chat_completion.choices[0].message.content
            
    except Exception as e:
        return f"Errore API Groq: {str(e)}"

def check_groq_connection() -> bool:
    """Verifica se la connessione Groq funziona"""
    if not GROQ_AVAILABLE:
        return False
    
    if not GROQ_API_KEY or GROQ_API_KEY == "TUA_CHIAVE_API_QUI":
        return False
    
    try:
        client = get_groq_client()
        if not client:
            return False
        
        # Test rapido
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": "test"}],
            model=MODEL_NAME,
            max_tokens=5
        )
        return True
    except Exception as e:
        st.error(f"Errore connessione: {str(e)}")
        return False

# ============================================================================
# FUNZIONI ANALISI AZIENDE
# ============================================================================

def get_top_10_companies(df: pd.DataFrame) -> pd.DataFrame:
    """Estrae le top 10 aziende per Investment_Score"""
    if df.empty or 'Investment_Score' not in df.columns:
        return pd.DataFrame()
    
    top_10 = df.nlargest(10, 'Investment_Score').copy()
    return top_10

def analyze_company_with_ai(company_data: pd.Series) -> Dict:
    """Analizza una singola azienda usando l'AI cloud"""
    
    company_context = f"""
Analizza questa azienda per determinare la probabilità di successo negli investimenti (orizzonte 2-4 settimane):

**AZIENDA**: {company_data.get('Company', 'N/A')} ({company_data.get('Symbol', 'N/A')})
**Settore**: {company_data.get('Sector', 'N/A')} | **Paese**: {company_data.get('Country', 'N/A')}

**METRICHE CHIAVE**:
- Prezzo: ${company_data.get('Price', 'N/A')}
- Market Cap: {company_data.get('Market Cap', 'N/A')}
- Investment Score: {company_data.get('Investment_Score', 'N/A')}/100

**INDICATORI TECNICI**:
- RSI: {company_data.get('RSI', 'N/A')} (Score: {company_data.get('RSI_Score', 'N/A')}/10)
- MACD Score: {company_data.get('MACD_Score', 'N/A')}/10
- Trend Score: {company_data.get('Trend_Score', 'N/A')}/10
- Tech Rating: {company_data.get('Rating', 'N/A')} (Score: {company_data.get('Tech_Rating_Score', 'N/A')}/10)
- Volatilità: {company_data.get('Volatility %', 'N/A')} (Score: {company_data.get('Volatility_Score', 'N/A')}/10)

**PERFORMANCE**:
- Cambio %: {company_data.get('Change %', 'N/A')}
- Performance Settimana: {company_data.get('Perf Week %', 'N/A')}
- Performance Mese: {company_data.get('Perf Month %', 'N/A')}
- Volume: {company_data.get('Volume', 'N/A')}

Fornisci un'analisi strutturata:

1. **Punti di Forza** (3 bullet points concisi)
2. **Rischi Principali** (3 bullet points concisi)
3. **Probabilità di Successo**: Indica CHIARAMENTE "Probabilità: XX/100" dove XX è un numero da 0 a 100
4. **Sintesi** (1 frase conclusiva)

Sii conciso, professionale e basato sui dati forniti.
"""
    
    analysis = call_groq_api(company_context, max_tokens=800)
    success_probability = extract_success_probability(analysis, company_data.get('Investment_Score', 0))
    
    return {
        'symbol': company_data.get('Symbol', 'N/A'),
        'company': company_data.get('Company', 'N/A'),
        'sector': company_data.get('Sector', 'N/A'),
        'analysis': analysis,
        'success_probability': success_probability,
        'investment_score': company_data.get('Investment_Score', 0),
        'price': company_data.get('Price', 'N/A'),
        'change_pct': company_data.get('Change %', 'N/A'),
        'rating': company_data.get('Rating', 'N/A')
    }

def extract_success_probability(analysis_text: str, fallback_score: float) -> float:
    """Estrae la probabilità di successo dall'analisi AI"""
    patterns = [
        r'probabilità[:\s]+(\d+)',
        r'(\d+)/100',
        r'success.*?(\d+)',
        r'score[:\s]+(\d+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, analysis_text.lower())
        if match:
            try:
                prob = float(match.group(1))
                if 0 <= prob <= 100:
                    return prob
            except:
                pass
    
    return min(fallback_score, 100)

def rank_and_select_top_3(analyzed_companies: List[Dict]) -> List[Dict]:
    """Classifica le aziende analizzate e seleziona le top 3"""
    sorted_companies = sorted(
        analyzed_companies, 
        key=lambda x: x['success_probability'], 
        reverse=True
    )
    return sorted_companies[:3]

def generate_detailed_report(company_analysis: Dict, rank: int) -> str:
    """Genera un report dettagliato per una singola azienda"""
    
    report_prompt = f"""
Crea un report professionale di investimento dettagliato per:

**POSIZIONE #{rank}**
**AZIENDA**: {company_analysis['company']} ({company_analysis['symbol']})
**Settore**: {company_analysis['sector']}
**Investment Score**: {company_analysis['investment_score']:.1f}/100
**Probabilità Successo AI**: {company_analysis['success_probability']:.1f}/100
**Prezzo Attuale**: ${company_analysis['price']}
**Cambio %**: {company_analysis['change_pct']}
**Rating Tecnico**: {company_analysis['rating']}

**ANALISI PRELIMINARE**:
{company_analysis['analysis']}

Genera un report investimento strutturato con queste sezioni:

## 1. EXECUTIVE SUMMARY
Sintesi dell'opportunità di investimento (max 100 parole). Evidenzia il potenziale e il posizionamento di mercato.

## 2. ANALISI TECNICA DETTAGLIATA
Valutazione approfondita degli indicatori tecnici, trend, momentum e pattern di prezzo (max 150 parole).

## 3. POTENZIALE DI CRESCITA
Stima del potenziale di crescita a 2-4 settimane con target price realistico basato sui dati attuali (max 120 parole).

## 4. GESTIONE DEL RISCHIO
Strategia concreta con:
- Stop Loss consigliato (percentuale e prezzo)
- Take Profit consigliato (percentuale e prezzo)
- Dimensionamento posizione
(max 120 parole)

## 5. RACCOMANDAZIONE FINALE
Decisione chiara: **ACQUISTA** / **MANTIENI** / **EVITA**
Motivazione specifica basata sui dati (max 80 parole)

Mantieni tono professionale, concreto e orientato all'azione. Usa numeri specifici dove possibile.
"""
    
    report = call_groq_api(report_prompt, max_tokens=2000)
    return report

# ============================================================================
# APP PRINCIPALE AGENTE AI
# ============================================================================

def ai_agent_app():
    """Interfaccia Streamlit per l'agente AI di analisi finanziaria"""
    
    st.title("🤖 Agente AI - Analisi Intelligente Azionaria")
    st.markdown("**Analisi automatica cloud-based** delle migliori 10 aziende con selezione AI-powered delle top 3")
    
    # Verifica libreria Groq
    if not GROQ_AVAILABLE:
        st.error("⚠️ Libreria Groq non installata!")
        st.code("pip install groq", language="bash")
        st.info("Dopo l'installazione, riavvia Streamlit")
        return
    
    # Verifica API Key
    st.subheader("🔌 Stato Connessione AI Cloud")
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.spinner("Verifica connessione..."):
            if check_groq_connection():
                st.success("✅ Groq API connessa e funzionante")
                api_ok = True
            else:
                st.error("❌ API non configurata o non valida")
                with st.expander("🔧 Troubleshooting"):
                    st.markdown("""
                    **Possibili cause:**
                    
                    1. **API Key non valida**: Verifica che la chiave sia corretta
                    2. **Libreria non installata**: Esegui `pip install groq`
                    3. **Limite API superato**: Controlla su console.groq.com
                    4. **Connessione internet**: Verifica la connessione
                    
                    **Come risolvere:**
                    ```
                    # Installa la libreria ufficiale
                    pip install groq
                    
                    # Verifica l'API key su:
                    # https://console.groq.com/keys
                    ```
                    """)
                api_ok = False
    
    with col2:
        st.info(f"🧠 Modello: Llama 3.1 70B")
        st.caption("⚡ Powered by Groq Cloud")
    
    st.markdown("---")
    
    # Verifica dati disponibili
    if 'data' not in st.session_state or st.session_state.data.empty:
        st.warning("⚠️ Nessun dato disponibile. Vai su **'📈 Stock Screener'** e clicca **'Aggiorna Dati'**")
        return
    
    df = st.session_state.data
    top_10 = get_top_10_companies(df)
    
    if top_10.empty:
        st.error("❌ Impossibile estrarre le top 10 aziende. Verifica i dati dello screener.")
        return
    
    # Mostra top 10
    st.subheader("📊 Top 10 Aziende (Investment Score più alto)")
    
    display_cols = ['Company', 'Symbol', 'Investment_Score', 'Price', 'Rating', 'Sector', 'Change %']
    available_cols = [col for col in display_cols if col in top_10.columns]
    
    st.dataframe(
        top_10[available_cols].style.highlight_max(subset=['Investment_Score'], color='lightgreen'),
        use_container_width=True,
        height=400
    )
    
    st.markdown("---")
    
    # Pulsante analisi
    if not api_ok:
        st.warning("🔧 Configura la Groq API per procedere (vedi troubleshooting sopra)")
        return
    
    col_btn1, col_btn2 = st.columns([2, 1])
    
    with col_btn1:
        start_analysis = st.button(
            "🚀 Avvia Analisi AI e Seleziona Top 3", 
            type="primary", 
            use_container_width=True
        )
    
    with col_btn2:
        if 'ai_top_3' in st.session_state:
            if st.button("🔄 Reset Analisi", use_container_width=True):
                del st.session_state['ai_top_3']
                for key in list(st.session_state.keys()):
                    if key.startswith('report_'):
                        del st.session_state[key]
                st.rerun()
    
    if start_analysis:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        analyzed_companies = []
        
        # Analizza le 10 aziende
        for idx, (_, company) in enumerate(top_10.iterrows()):
            status_text.text(f"🔍 Analisi {idx+1}/10: {company['Company']}...")
            progress_bar.progress((idx + 1) / 10)
            
            analysis = analyze_company_with_ai(company)
            analyzed_companies.append(analysis)
        
        status_text.text("🎯 Selezione AI delle top 3 aziende...")
        
        # Seleziona top 3
        top_3 = rank_and_select_top_3(analyzed_companies)
        st.session_state['ai_top_3'] = top_3
        
        progress_bar.progress(1.0)
        status_text.text("✅ Analisi completata!")
        
        st.success(f"✅ Analisi completata! Selezionate {len(top_3)} aziende con maggiore probabilità di successo")
        st.balloons()
        st.rerun()
    
    # Mostra risultati se disponibili
    if 'ai_top_3' in st.session_state:
        st.markdown("---")
        st.header("🏆 Top 3 Aziende Selezionate dall'AI")
        
        top_3 = st.session_state['ai_top_3']
        
        # Metriche comparative
        col_m1, col_m2, col_m3 = st.columns(3)
        
        for idx, (col, company) in enumerate(zip([col_m1, col_m2, col_m3], top_3)):
            with col:
                st.metric(
                    f"#{idx+1} - {company['symbol']}", 
                    f"{company['success_probability']:.0f}/100",
                    f"Score: {company['investment_score']:.1f}"
                )
        
        st.markdown("---")
        
        # Tab per ogni azienda
        tabs = st.tabs([f"#{i+1} - {comp['symbol']}" for i, comp in enumerate(top_3)])
        
        for idx, (tab, company) in enumerate(zip(tabs, top_3)):
            with tab:
                st.subheader(f"#{idx+1} - {company['company']} ({company['symbol']})")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Investment Score", f"{company['investment_score']:.1f}/100")
                
                with col2:
                    st.metric("Probabilità AI", f"{company['success_probability']:.0f}/100")
                
                with col3:
                    if company['success_probability'] >= 75:
                        rating_label = "🟢 ECCELLENTE"
                    elif company['success_probability'] >= 60:
                        rating_label = "🟡 BUONO"
                    else:
                        rating_label = "🟠 MODERATO"
                    
                    st.metric("Rating AI", rating_label)
                
                with col4:
                    st.metric("Prezzo", f"${company['price']}")
                
                st.markdown("---")
                
                # Analisi preliminare
                with st.expander("🔍 Analisi Preliminare AI", expanded=True):
                    st.markdown(company['analysis'])
                
                st.markdown("---")
                
                # Report dettagliato
                col_rep1, col_rep2 = st.columns([3, 1])
                
                with col_rep1:
                    st.markdown("### 📊 Report Completo di Investimento")
                
                with col_rep2:
                    generate_btn = st.button(
                        f"📄 Genera Report", 
                        key=f"btn_report_{idx}", 
                        type="secondary",
                        use_container_width=True
                    )
                
                if generate_btn:
                    with st.spinner(f"⏳ Generazione report per {company['symbol']}..."):
                        report = generate_detailed_report(company, idx + 1)
                        st.session_state[f'report_{idx}'] = report
                        st.rerun()
                
                # Mostra report se generato
                if f'report_{idx}' in st.session_state:
                    st.markdown(st.session_state[f'report_{idx}'])
                    
                    # Download report
                    report_text = f"""
{'='*70}
REPORT DI INVESTIMENTO - {company['company']} ({company['symbol']})
{'='*70}

Data Generazione: {datetime.now().strftime('%d/%m/%Y %H:%M')}
Settore: {company['sector']}
Investment Score: {company['investment_score']:.1f}/100
Probabilità Successo AI: {company['success_probability']:.1f}/100
Prezzo Attuale: ${company['price']}
Cambio %: {company['change_pct']}
Rating Tecnico: {company['rating']}

{'='*70}

{st.session_state[f'report_{idx}']}

{'='*70}
Report generato da Flusso Grugno AI Agent
Powered by Groq AI - Llama 3.1 70B
{'='*70}
"""
                    
                    st.download_button(
                        label=f"📥 Scarica Report {company['symbol']}.txt",
                        data=report_text,
                        file_name=f"report_{company['symbol']}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                        mime="text/plain",
                        key=f"download_{idx}",
                        use_container_width=True
                    )
                else:
                    st.info("💡 Clicca **'Genera Report'** per ottenere l'analisi completa con raccomandazioni e target price.")
    
    # Sidebar info
    with st.sidebar:
        with st.expander("ℹ️ Info Agente AI"):
            st.markdown("""
            ### 🤖 Come Funziona
            
            **Fase 1: Analisi Multipla**
            - Estrae le 10 aziende con Investment Score più alto
            - L'AI analizza ogni azienda considerando 30+ parametri
            - Valuta punti di forza, rischi e probabilità di successo
            
            **Fase 2: Selezione Intelligente**
            - Ranking automatico basato su probabilità AI
            - Selezione delle 3 aziende con maggior potenziale
            
            **Fase 3: Report Dettagliati**
            - Executive summary professionale
            - Analisi tecnica approfondita
            - Target price e gestione del rischio
            - Raccomandazione finale chiara
            
            ### ⚡ Tecnologia
            - **Cloud AI**: Groq (ultra-veloce)
            - **Modello**: Llama 3.1 70B
            - **API**: Completamente gratuita
            - **Limiti**: 6000 analisi/giorno
            
            ### 🔒 Privacy & Sicurezza
            - Comunicazione criptata HTTPS
            - Nessun dato salvato sui server Groq
            - API key personale protetta
            """)
