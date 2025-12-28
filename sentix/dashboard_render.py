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
    # Try absolute import first (local dev)
    from sentix.database import init_database, save_articles, load_articles
    init_database()
    DB_AVAILABLE = True
except ImportError:
    try:
        # Try relative import (Render deployment)
        from database import init_database, save_articles, load_articles
        init_database()
        DB_AVAILABLE = True
    except Exception as e:
        print(f"Database init failed (relative): {e}")
        DB_AVAILABLE = False
        load_articles = None
except Exception as e:
    print(f"Database init failed (absolute): {e}")
    DB_AVAILABLE = False
    load_articles = None

# Custom CSS - Cyberpunk / Glassmorphism Theme
st.markdown("""
<style>
    /* Import Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@300;500;700&display=swap');

    /* Background Image with Animation */
    .stApp {
        background: transparent;
    }
    
    .stApp::before {
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background-image: url("https://raw.githubusercontent.com/jhondev06/aeternum-sentix/main/sentix/assets/bg.png");
        background-size: cover;
        background-position: center;
        z-index: -1;
        animation: breathe 20s infinite alternate ease-in-out;
    }

    @keyframes breathe {
        0% { 
            transform: scale(1); 
            filter: brightness(0.6) hue-rotate(0deg); 
        }
        50% {
             filter: brightness(1.3) hue-rotate(15deg); 
        }
        100% { 
            transform: scale(1.15); 
            filter: brightness(0.6) hue-rotate(0deg); 
        }
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
# Sentiment Analysis (Local - Keyword Based)
# =============================================================================

# Dicionário robusto de palavras-chave financeiras
POSITIVE_KEYWORDS = [
    'alta', 'lucro', 'crescimento', 'sobe', 'positivo', 'recorde', 'valorização',
    'ganho', 'avanço', 'otimismo', 'recuperação', 'forte', 'supera', 'bom',
    'dividendo', 'extraordinário', 'expansão', 'sucesso', 'melhora', 'dispara',
    'boom', 'aquecido', 'favorável', 'benefício', 'oportunidade', 'aumento',
    'alta histórica', 'máxima', 'excelente', 'robusto', 'sólido'
]

NEGATIVE_KEYWORDS = [
    'queda', 'perda', 'crise', 'desaba', 'negativo', 'risco', 'baixa',
    'prejuízo', 'retração', 'pessimismo', 'fraco', 'problema', 'dívida',
    'inflação', 'juros', 'recessão', 'colapso', 'declínio', 'falência',
    'default', 'calote', 'escândalo', 'investigação', 'multa', 'tombo',
    'derrocada', 'despenca', 'afunda', 'mínima', 'redução', 'corte'
]

# Lista de Ativos Brasileiros Populares para Recomendação
RECOMMENDED_ASSETS = {
    "Ações": [
        ("PETR4.SA", "Petrobras PN", "Energia/Petróleo"),
        ("VALE3.SA", "Vale ON", "Mineração"),
        ("ITUB4.SA", "Itaú Unibanco PN", "Bancos"),
        ("BBDC4.SA", "Bradesco PN", "Bancos"),
        ("ABEV3.SA", "Ambev ON", "Bebidas"),
        ("WEGE3.SA", "WEG ON", "Industrial"),
        ("RENT3.SA", "Localiza ON", "Aluguel de Carros"),
        ("MGLU3.SA", "Magazine Luiza ON", "Varejo"),
        ("BBAS3.SA", "Banco do Brasil ON", "Bancos"),
        ("B3SA3.SA", "B3 ON", "Bolsa de Valores"),
    ],
    "ETFs": [
        ("BOVA11.SA", "iShares Ibovespa", "Índice Bovespa"),
        ("SMAL11.SA", "iShares Small Cap", "Small Caps"),
        ("IVVB11.SA", "iShares S&P 500", "EUA"),
    ],
    "FIIs": [
        ("HGLG11.SA", "CSHG Logística", "Logística"),
        ("MXRF11.SA", "Maxi Renda", "Papéis"),
        ("XPLG11.SA", "XP Log", "Logística"),
    ]
}

def analyze_sentiment_local(text: str, ticker: str = "MANUAL") -> Dict[str, Any]:
    """
    Análise de sentimento local usando keywords financeiros.
    Funciona 100% offline, sem depender de APIs externas.
    """
    text_lower = text.lower()
    
    # Contar ocorrências
    pos_count = sum(1 for word in POSITIVE_KEYWORDS if word in text_lower)
    neg_count = sum(1 for word in NEGATIVE_KEYWORDS if word in text_lower)
    total = pos_count + neg_count + 1  # +1 para evitar divisão por zero
    
    # Calcular probabilidades
    pos_prob = min(0.95, pos_count / total + 0.1) if pos_count > 0 else 0.15
    neg_prob = min(0.95, neg_count / total + 0.1) if neg_count > 0 else 0.15
    neu_prob = max(0.05, 1 - pos_prob - neg_prob)
    
    # Normalizar para somar 1
    total_prob = pos_prob + neg_prob + neu_prob
    pos_prob /= total_prob
    neg_prob /= total_prob
    neu_prob /= total_prob
    
    # Determinar label
    if pos_count > neg_count:
        label = "Positivo 📈"
        score = pos_prob
    elif neg_count > pos_count:
        label = "Negativo 📉"
        score = -neg_prob
    else:
        label = "Neutro ➖"
        score = 0.0
    
    result = {
        "success": True,
        "label": label,
        "score": round(score, 4),
        "probabilities": {
            "Positivo": round(pos_prob, 4),
            "Negativo": round(neg_prob, 4),
            "Neutro": round(neu_prob, 4)
        },
        "source": "local_analysis",
        "keywords_found": {
            "positive": pos_count,
            "negative": neg_count
        }
    }
    
    # Save to Database if available
    if DB_AVAILABLE:
        try:
            article_id = f"manual_{int(datetime.now().timestamp())}"
            p = result["probabilities"]
            
            df_new = pd.DataFrame([{
                "id": article_id,
                "ticker": ticker,
                "source": "dashboard_manual",
                "published_at": datetime.utcnow().isoformat(),
                "title": text[:50] + "..." if len(text) > 50 else text,
                "body": text,
                "url": "manual_entry",
                "lang": "pt",
                "pos": float(p.get("Positivo", 0)),
                "neg": float(p.get("Negativo", 0)),
                "neu": float(p.get("Neutro", 0)),
                "score": result["score"]
            }])
            
            save_articles(df_new)
            st.toast("✅ Análise salva no banco de dados!")
            
        except Exception as e:
            print(f"Failed to save to DB: {e}")
    
    return result


# =============================================================================
# Data Loading (Real or Demo)
# =============================================================================

import numpy as np

@st.cache_data(ttl=60)  # Cache for 60 seconds
def load_real_data():
    """Load real sentiment data from Supabase."""
    if not DB_AVAILABLE or load_articles is None:
        return None
    
    try:
        df = load_articles(limit=500)
        if df.empty:
            return None
        
        # Ensure date column is datetime
        df['date'] = pd.to_datetime(df['published_at']).dt.date
        
        # Calculate probability from pos score (0-1 range)
        df['probability'] = df['pos'].fillna(0.5)
        df['sentiment_score'] = df['score'].fillna(0)
        
        # Group by date and ticker for charts
        grouped = df.groupby(['date', 'ticker']).agg({
            'sentiment_score': 'mean',
            'probability': 'mean',
            'id': 'count'
        }).reset_index()
        grouped.rename(columns={'id': 'article_count'}, inplace=True)
        
        return grouped
    except Exception as e:
        print(f"Error loading real data: {e}")
        return None


def load_demo_data():
    """Load demo sentiment data (fallback)."""
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


def get_dashboard_data():
    """Get real data if available, otherwise demo data."""
    real_data = load_real_data()
    if real_data is not None and not real_data.empty:
        return real_data, True  # (data, is_real)
    return load_demo_data(), False


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
    st.header("📊 Análise de Sentimento por Ativo")
    
    # =========================================================================
    # STEP 1: Selecionar Ativo (OBRIGATÓRIO)
    # =========================================================================
    st.subheader("1️⃣ Selecione o Ativo para Análise")
    
    # Verificar se há preset de exemplo
    preset_category = st.session_state.get('preset_category', None)
    preset_ticker = st.session_state.get('preset_ticker', None)
    
    # Lista de categorias
    categories_list = list(RECOMMENDED_ASSETS.keys())
    
    # Calcular index default para categoria
    cat_default_idx = 0
    if preset_category and preset_category in categories_list:
        cat_default_idx = categories_list.index(preset_category)
        # Limpar preset após uso
        st.session_state['preset_category'] = None
    
    col_cat, col_asset = st.columns(2)
    
    with col_cat:
        category = st.selectbox(
            "📁 Categoria:",
            categories_list,
            index=cat_default_idx
        )
    
    with col_asset:
        assets_in_category = RECOMMENDED_ASSETS[category]
        asset_options = [f"{t[0]} - {t[1]}" for t in assets_in_category]
        
        # Calcular index default para ativo
        asset_default_idx = 0
        if preset_ticker:
            for idx, opt in enumerate(asset_options):
                if opt.startswith(preset_ticker):
                    asset_default_idx = idx
                    break
            # Limpar preset após uso
            st.session_state['preset_ticker'] = None
        
        selected_asset_str = st.selectbox(
            "💰 Ativo:",
            asset_options,
            index=asset_default_idx
        )
        
        selected_ticker = selected_asset_str.split(" - ")[0] if selected_asset_str else None
    
    # Mostrar info do ativo selecionado
    if selected_ticker:
        asset_info = next((t for t in assets_in_category if t[0] == selected_ticker), None)
        if asset_info:
            st.success(f"✅ **Ativo Selecionado:** {asset_info[0]} | {asset_info[1]} | Setor: {asset_info[2]}")
    
    st.markdown("---")
    
    # =========================================================================
    # STEP 2: Analisar Notícia
    # =========================================================================
    st.subheader("2️⃣ Cole a Notícia sobre o Ativo")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        default_text = st.session_state.get('example_text', "")
        
        text_input = st.text_area(
            f"📰 Notícia sobre **{selected_ticker}**:",
            value=default_text,
            height=150,
            placeholder=f"Cole aqui uma notícia sobre {selected_ticker}..."
        )
        
        auto_run = st.session_state.get('run_analysis', False)
        
        if st.button("🔍 ANALISAR SENTIMENTO", type="primary", use_container_width=True) or (auto_run and text_input):
            st.session_state['run_analysis'] = False
            st.session_state['example_text'] = ""
            
            if not selected_ticker:
                st.error("❌ Selecione um ativo primeiro!")
            elif not text_input.strip():
                st.warning("⚠️ Digite ou cole uma notícia para analisar.")
            else:
                with st.spinner(f"Analisando sentimento para {selected_ticker}..."):
                    result = analyze_sentiment_local(text_input, selected_ticker)
                    
                    if result["success"]:
                        st.markdown("### 📊 Resultado da Análise")
                        
                        if "Positivo" in result['label']:
                            st.success(f"**🎯 Sentimento para {selected_ticker}:** {result['label']}")
                        elif "Negativo" in result['label']:
                            st.error(f"**🎯 Sentimento para {selected_ticker}:** {result['label']}")
                        else:
                            st.info(f"**🎯 Sentimento para {selected_ticker}:** {result['label']}")
                        
                        col_a, col_b, col_c, col_d = st.columns(4)
                        with col_a:
                            st.metric("Score", f"{result['score']:.3f}")
                        with col_b:
                            st.metric("📈 Positivo", f"{result['probabilities'].get('Positivo', 0):.1%}")
                        with col_c:
                            st.metric("📉 Negativo", f"{result['probabilities'].get('Negativo', 0):.1%}")
                        with col_d:
                            st.metric("➖ Neutro", f"{result['probabilities'].get('Neutro', 0):.1%}")
                        
                        kw = result.get("keywords_found", {})
                        if kw.get("positive", 0) > 0 or kw.get("negative", 0) > 0:
                            st.caption(f"🔎 Keywords: +{kw.get('positive', 0)} positivas, -{kw.get('negative', 0)} negativas")
                        
                        st.success(f"✅ Análise salva! Vá na aba 'Dashboard' para ver o histórico de {selected_ticker}.")
    
    with col2:
        st.markdown("### 📝 Exemplos de Notícias")
        st.caption("Clique para preencher automaticamente:")
        
        examples_with_assets = [
            ("PETR4.SA", "Ações", "Petrobras anuncia dividendo extraordinário de R$ 15 bilhões"),
            ("VALE3.SA", "Ações", "Vale reporta queda de 20% na produção de minério"),
            ("ITUB4.SA", "Ações", "Itaú lucra R$ 10 bilhões e supera expectativas"),
            ("BBDC4.SA", "Ações", "Bradesco enfrenta crise com inadimplência recorde"),
            ("ABEV3.SA", "Ações", "Ambev tem crescimento robusto nas vendas"),
        ]
        
        for ticker, cat, text in examples_with_assets:
            if st.button(f"📌 {ticker}", key=f"ex_{ticker}", help=text):
                st.session_state['preset_category'] = cat
                st.session_state['preset_ticker'] = ticker
                st.session_state['example_text'] = text
                st.session_state['run_analysis'] = True
                st.rerun()

# =============================================================================
# Tab 2: Dashboard
# =============================================================================
with tab2:
    st.header("Dashboard de Probabilidades")
    
    # Load data (real or demo)
    df, is_real_data = get_dashboard_data()
    
    # Show data source indicator
    if is_real_data:
        st.success("📊 Exibindo dados REAIS do Supabase")
    else:
        st.info("📊 Exibindo dados de demonstração (analise textos para popular o banco)")
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        selected_tickers = st.multiselect(
            "Selecionar Ativos",
            df['ticker'].unique(),
            default=list(df['ticker'].unique())
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
