"""
Sentix Dashboard for Render - Light Version
Uses HuggingFace Space API for sentiment analysis
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import requests
from typing import Dict, Any, Optional

# =============================================================================
# Configuration
# =============================================================================

# HuggingFace Space URL
HF_SPACE_URL = os.environ.get("HF_SPACE_URL", "https://your-username-sentix-finbert.hf.space")

# Initialize Database
try:
    from sentix.database import init_database, save_articles
    init_database()
    DB_AVAILABLE = True
except Exception as e:
    print(f"Database init failed: {e}")
    DB_AVAILABLE = False

# Custom CSS - Cyberpunk / Glassmorphism Theme
st.markdown("""
<style>
    /* Import Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@300;500;700&display=swap');

    /* Background Image */
    .stApp {
        background-image: url("https://raw.githubusercontent.com/jhondev06/aeternum-sentix/main/sentix/assets/bg.png");
        background-attachment: fixed;
        background-size: cover;
    }

    /* Glassmorphism Containers */
    .stMarkdown, .stDataFrame, .stPlotlyChart, div[data-testid="stMetric"], .stTextInput > div > div {
        background: rgba(16, 20, 30, 0.75);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(0, 255, 255, 0.1);
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5);
    }
    
    /* Input Field Special Style */
    .stTextInput > div > div > input {
        color: #00ffff !important;
        font-family: 'Rajdhani', sans-serif;
        font-size: 1.2rem;
    }

    /* Typography - Neon Headers */
    h1, h2, h3 {
        font-family: 'Orbitron', sans-serif !important;
        color: #fff !important;
        text-shadow: 0 0 10px rgba(0, 255, 255, 0.7), 0 0 20px rgba(0, 255, 255, 0.5);
        letter-spacing: 2px;
    }
    
    /* Custom Button - Cyberpunk Style */
    div.stButton > button {
        background: linear-gradient(45deg, #0b3d91, #00d4ff);
        color: white;
        font-family: 'Orbitron', sans-serif;
        border: none;
        border-radius: 5px;
        padding: 0.5rem 2rem;
        transition: all 0.3s ease;
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.5);
        text-transform: uppercase;
    }
    div.stButton > button:hover {
        background: linear-gradient(45deg, #00d4ff, #0b3d91);
        transform: scale(1.05);
        box-shadow: 0 0 25px rgba(0, 212, 255, 0.8);
    }

    /* Metric Values - Neon Green/Red */
    div[data-testid="stMetricValue"] {
        font-family: 'Orbitron', sans-serif;
        text-shadow: 0 0 10px currentColor;
    }

    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 10px;
        background: #0a0e17;
    }
    ::-webkit-scrollbar-thumb {
        background: #00d4ff;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# HuggingFace API Client & Persistence
# =============================================================================

def analyze_sentiment_hf(text: str) -> Dict[str, Any]:
    """
    Call HuggingFace Space API for sentiment analysis and save to DB.
    """
    result = {}
    error_msg = ""
    
    try:
        # Use Gradio client
        from gradio_client import Client
        
        client = Client(HF_SPACE_URL)
        api_result = client.predict(
            text=text,
            api_name="/predict"
        )
        
        # Result is (probabilities, label, score)
        probs, label, score = api_result
        
        result = {
            "success": True,
            "label": label,
            "score": float(score),
            "probabilities": probs,
            "source": "api"
        }
        
    except Exception as e:
        error_msg = str(e)
        st.warning(f"⚠️ API Info: {e}")
        
        # Fallback: simple keyword-based sentiment
        positive_words = ['alta', 'lucro', 'crescimento', 'sobe', 'positivo', 'recorde']
        negative_words = ['queda', 'perda', 'crise', 'desaba', 'negativo', 'risco']
        
        text_lower = text.lower()
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        
        fallback_probs = {"Positivo": 0.33, "Neutro": 0.34, "Negativo": 0.33}
        fallback_label = "Neutro ➖"
        fallback_score = 0.0
        
        if pos_count > neg_count:
            fallback_label, fallback_score = "Positivo 📈", 0.5
            fallback_probs = {"Positivo": 0.6, "Neutro": 0.3, "Negativo": 0.1}
        elif neg_count > pos_count:
            fallback_label, fallback_score = "Negativo 📉", -0.5
            fallback_probs = {"Positivo": 0.1, "Neutro": 0.3, "Negativo": 0.6}
            
        result = {
            "success": True, # Still assume success for UI 
            "label": fallback_label,
            "score": fallback_score,
            "probabilities": fallback_probs,
            "source": "fallback",
            "error": error_msg
        }

    # Save to Database if available
    if DB_AVAILABLE:
        try:
            # Create a simple unique ID based on timestamp
            article_id = f"manual_{int(datetime.now().timestamp())}"
            
            # Map probabilities to flat columns
            p = result["probabilities"]
            
            df_new = pd.DataFrame([{
                "id": article_id,
                "ticker": "MANUAL", # Tag as manual entry
                "source": "dashboard_manual",
                "published_at": datetime.utcnow().isoformat(),
                "title": text[:50] + "...",
                "body": text,
                "url": "manual_entry",
                "lang": "pt",
                "pos": float(p.get("Positivo", 0)),
                "neg": float(p.get("Negativo", 0)),
                "neu": float(p.get("Neutro", 0)),
                "score": result["score"]
            }])
            
            save_articles(df_new)
            st.toast("✅ Salvo no Banco de Dados!")
            
        except Exception as e:
            print(f"Failed to save to DB: {e}")
            st.error(f"Erro ao salvar no banco: {e}")

    return result


# =============================================================================
# Demo Data
# =============================================================================

@st.cache_data
def load_demo_data():
    """Load demo sentiment data."""
    dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
    
    data = {
        'date': list(dates) * 3,
        'ticker': ['PETR4.SA'] * 30 + ['VALE3.SA'] * 30 + ['ITUB4.SA'] * 30,
        'sentiment_score': list(np.random.uniform(-0.3, 0.5, 30)) + 
                          list(np.random.uniform(-0.2, 0.4, 30)) +
                          list(np.random.uniform(-0.1, 0.3, 30)),
        'probability': list(np.random.uniform(0.4, 0.7, 30)) +
                      list(np.random.uniform(0.45, 0.65, 30)) +
                      list(np.random.uniform(0.5, 0.6, 30)),
        'article_count': list(np.random.randint(3, 15, 30)) +
                        list(np.random.randint(2, 12, 30)) +
                        list(np.random.randint(1, 8, 30))
    }
    
    return pd.DataFrame(data)


import numpy as np


# =============================================================================
# Main App
# =============================================================================

st.markdown('<h1 class="main-header">📊 Sentix - Análise de Sentimento Financeiro</h1>', unsafe_allow_html=True)

# Sidebar
st.sidebar.header("⚙️ Configurações")
st.sidebar.markdown(f"**API:** {HF_SPACE_URL}")

# Tabs
tab1, tab2, tab3 = st.tabs(["🔍 Analisar Texto", "📈 Dashboard", "ℹ️ Sobre"])

# =============================================================================
# Tab 1: Text Analysis
# =============================================================================
with tab1:
    st.header("Análise de Sentimento em Tempo Real")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        text_input = st.text_area(
            "Digite ou cole uma notícia financeira:",
            height=150,
            placeholder="Ex: Petrobras anuncia lucro recorde no terceiro trimestre..."
        )
        
        if st.button("🔍 Analisar Sentimento", type="primary"):
            if text_input.strip():
                with st.spinner("Analisando..."):
                    result = analyze_sentiment_hf(text_input)
                    
                    if result["success"]:
                        st.success(f"**Sentimento:** {result['label']}")
                        
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.metric("Score", f"{result['score']:.3f}")
                        with col_b:
                            st.metric("Positivo", f"{result['probabilities'].get('Positivo', 0):.1%}")
                        with col_c:
                            st.metric("Negativo", f"{result['probabilities'].get('Negativo', 0):.1%}")
            else:
                st.warning("Digite um texto para analisar.")
    
    with col2:
        st.markdown("### 📝 Exemplos")
        
        examples = [
            "Petrobras anuncia dividendo extraordinário",
            "Inflação acelera e Banco Central eleva juros",
            "Ibovespa fecha estável aguardando Fed"
        ]
        
        for ex in examples:
            if st.button(ex, key=ex):
                st.session_state['example_text'] = ex
                st.rerun()

# =============================================================================
# Tab 2: Dashboard
# =============================================================================
with tab2:
    st.header("Dashboard de Probabilidades")
    
    # Load demo data
    df = load_demo_data()
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        selected_tickers = st.multiselect(
            "Selecionar Ativos",
            df['ticker'].unique(),
            default=df['ticker'].unique()
        )
    
    # Filter data
    filtered_df = df[df['ticker'].isin(selected_tickers)]
    
    # KPIs
    st.subheader("📊 Métricas Atuais")
    kpi_cols = st.columns(4)
    
    with kpi_cols[0]:
        avg_prob = filtered_df['probability'].mean()
        st.metric("Prob. Média de Subida", f"{avg_prob:.1%}")
    
    with kpi_cols[1]:
        avg_sent = filtered_df['sentiment_score'].mean()
        st.metric("Sentimento Médio", f"{avg_sent:+.3f}")
    
    with kpi_cols[2]:
        total_articles = filtered_df['article_count'].sum()
        st.metric("Artigos Analisados", f"{total_articles:,}")
    
    with kpi_cols[3]:
        tickers_count = len(selected_tickers)
        st.metric("Ativos Monitorados", tickers_count)
    
    # Charts
    st.subheader("📈 Evolução do Sentimento")
    
    fig = px.line(
        filtered_df,
        x='date',
        y='probability',
        color='ticker',
        title='Probabilidade de Subida por Ativo',
        template='plotly_white'
    )
    fig.update_layout(yaxis_tickformat='.0%', height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig2 = px.bar(
            filtered_df.groupby('ticker')['sentiment_score'].mean().reset_index(),
            x='ticker',
            y='sentiment_score',
            title='Sentimento Médio por Ativo',
            template='plotly_white',
            color='sentiment_score',
            color_continuous_scale='RdYlGn'
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    with col2:
        fig3 = px.pie(
            filtered_df.groupby('ticker')['article_count'].sum().reset_index(),
            values='article_count',
            names='ticker',
            title='Distribuição de Artigos'
        )
        st.plotly_chart(fig3, use_container_width=True)

# =============================================================================
# Tab 3: About
# =============================================================================
with tab3:
    st.header("Sobre o Sentix")
    
    st.markdown("""
    ### 🎯 O que é?
    
    O **Sentix** é uma plataforma de análise de sentimento financeiro que utiliza 
    inteligência artificial para prever movimentos de preços baseado no tom das notícias.
    
    ### 🧠 Tecnologia
    
    - **Modelo:** FinBERT (BERT fine-tuned para finanças)
    - **Hospedagem ML:** Hugging Face Spaces
    - **Dashboard:** Streamlit + Plotly
    - **Deploy:** Render
    
    ### 📊 Como funciona?
    
    1. Notícias são coletadas de fontes financeiras
    2. FinBERT analisa o sentimento de cada texto
    3. Scores são agregados por ativo e período
    4. Modelo ML prevê probabilidade de movimento
    
    ### 🔗 Links
    
    - [GitHub](https://github.com/jhondev06/aeternum-sentix)
    - [HuggingFace Space](https://huggingface.co/spaces/seu-usuario/sentix-finbert)
    """)

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**Sentix v2.0** | Powered by FinBERT")
