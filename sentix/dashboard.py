import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import yfinance as yf
import numpy as np
from models.prob_model import ProbModel
import os

# Page configuration
st.set_page_config(
    page_title="Sentix - Painel de Análise de Sentimento",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 0.25rem solid #1f77b4;
    }
    .alert-positive {
        background-color: #d4edda;
        color: #155724;
        padding: 0.75rem;
        border-radius: 0.25rem;
        border: 1px solid #c3e6cb;
    }
    .alert-negative {
        background-color: #f8d7da;
        color: #721c24;
        padding: 0.75rem;
        border-radius: 0.25rem;
        border: 1px solid #f5c6cb;
    }
</style>
""", unsafe_allow_html=True)

# Load data
@st.cache_data
def load_sentiment_data():
    df = pd.read_csv('data/sentiment_bars.csv')
    df['bucket_start'] = pd.to_datetime(df['bucket_start'], errors='coerce')
    df['bucket_start'] = df['bucket_start'].dt.tz_localize(None)
    # Keep bucket_start as naive datetime for proper filtering/plotting
    return df

@st.cache_data
def load_prob_model():
    model_path = 'outputs/prob_model.pkl'
    if os.path.exists(model_path):
        return ProbModel.load(model_path)
    else:
        st.error("Modelo de probabilidade não encontrado. Execute o treinamento primeiro.")
        return None

@st.cache_data
def calculate_probabilities(df, _model):
    if _model is None:
        return df
    # Selecionar features
    features = ['mean_sent', 'std_sent', 'min_sent', 'max_sent', 'count', 'unc_mean', 'time_decay_mean']
    X = df[features].fillna(0)
    probs = _model.predict_proba(X)
    df = df.copy()
    df['probability'] = probs
    return df

@st.cache_data
def load_price_data(symbol, period='6mo'):
    try:
        data = yf.download(symbol, period=period)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)
        data.reset_index(inplace=True)
        data['Date'] = data['Date'].dt.tz_localize(None)  # Make datetime naive to match sentiment data
        return data
    except:
        return pd.DataFrame()

# Main app
st.markdown('<h1 class="main-header">📊 Sentix - Dashboard de Probabilidades de Ações</h1>', unsafe_allow_html=True)

# Load data
sentiment_df = load_sentiment_data()
prob_model = load_prob_model()
sentiment_df = calculate_probabilities(sentiment_df, prob_model)

# Sidebar filters
st.sidebar.header("🔧 Filtros")

# Entity filter
entities = sentiment_df['ticker'].unique()
selected_entities = st.sidebar.multiselect("Selecionar Ativos", entities, default=entities)

# Date filter
min_date = sentiment_df['bucket_start'].min().date()
max_date = sentiment_df['bucket_start'].max().date()
date_range = st.sidebar.date_input("Selecionar Período", [min_date, max_date])

if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

# Filter data
filtered_df = sentiment_df[
    (sentiment_df['ticker'].isin(selected_entities)) &
    (sentiment_df['bucket_start'].dt.date >= start_date) &
    (sentiment_df['bucket_start'].dt.date <= end_date)
]

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Visão Geral", "📊 Análise de Probabilidades", "🔄 Comparações", "✅ Validação", "📋 Dados"])

with tab1:
    st.header("Visão Geral do Painel")
    
    # KPIs
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        current_prob = filtered_df['probability'].iloc[-1] if not filtered_df.empty and 'probability' in filtered_df.columns else 0
        st.metric("Probabilidade Atual de Subida", f"{current_prob:.1%}")

    with col2:
        avg_prob = filtered_df['probability'].mean() if not filtered_df.empty and 'probability' in filtered_df.columns else 0
        st.metric("Probabilidade Média", f"{avg_prob:.1%}")

    with col3:
        current_sent = filtered_df['mean_sent'].iloc[-1] if not filtered_df.empty else 0
        st.metric("Sentimento Atual", f"{current_sent:.3f}")

    with col4:
        total_volume = filtered_df['count'].sum() if not filtered_df.empty else 0
        st.metric("Volume Total", f"{total_volume}")

    # Alerts
    if not filtered_df.empty and 'probability' in filtered_df.columns:
        latest_prob = filtered_df['probability'].iloc[-1]
        if latest_prob > 0.6:
            st.markdown('<div class="alert-positive">🚀 Alta probabilidade de subida! Considere posições compradas.</div>', unsafe_allow_html=True)
        elif latest_prob < 0.4:
            st.markdown('<div class="alert-negative">⚠️ Alta probabilidade de descida! Considere posições vendidas.</div>', unsafe_allow_html=True)
    
    # Quick charts
    col1, col2 = st.columns(2)

    with col1:
        if not filtered_df.empty and 'probability' in filtered_df.columns:
            fig = px.line(filtered_df, x='bucket_start', y='probability', color='ticker',
                          title='Evolução da Probabilidade de Subida', template='plotly_white')
            fig.update_layout(height=300, yaxis_tickformat='.1%')
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if not filtered_df.empty:
            fig = px.line(filtered_df, x='bucket_start', y='mean_sent', color='ticker',
                          title='Evolução do Sentimento', template='plotly_white')
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("Análise de Probabilidades")

    col1, col2 = st.columns(2)

    with col1:
        if not filtered_df.empty and 'probability' in filtered_df.columns:
            fig = px.histogram(filtered_df, x='probability', nbins=20, title='Distribuição da Probabilidade de Subida',
                                template='plotly_white', color_discrete_sequence=['#1f77b4'])
            fig.update_layout(height=400, xaxis_tickformat='.1%')
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if not filtered_df.empty and 'probability' in filtered_df.columns:
            fig = px.box(filtered_df, x='ticker', y='probability', title='Probabilidade por Ativo',
                          template='plotly_white', color='ticker')
            fig.update_layout(height=400, yaxis_tickformat='.1%')
            st.plotly_chart(fig, use_container_width=True)

    # Probabilidade vs Sentimento
    if not filtered_df.empty and 'probability' in filtered_df.columns:
        fig = px.scatter(filtered_df, x='mean_sent', y='probability', color='ticker',
                         title='Correlação: Sentimento vs Probabilidade de Subida', template='plotly_white')
        fig.update_layout(height=400, xaxis_title='Sentimento', yaxis_title='Probabilidade', yaxis_tickformat='.1%')
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.header("Comparações e Correlações")
    
    # Probabilidade vs Price
    stock_entities = [e for e in entities if e.endswith('.SA')]
    if stock_entities:
        selected_entity = st.selectbox("Selecionar Ação para Comparação", stock_entities)

        if selected_entity:
            price_df = load_price_data(selected_entity)
            if not price_df.empty:
                sent_entity = sentiment_df[sentiment_df['ticker'] == selected_entity]
                merged_df = pd.merge(sent_entity, price_df, left_on='bucket_start', right_on='Date', how='inner')

                if not merged_df.empty and 'probability' in merged_df.columns:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=merged_df['bucket_start'], y=merged_df['probability'],
                                            mode='lines', name='Probabilidade de Subida', line=dict(color='#1f77b4')))
                    fig.add_trace(go.Scatter(x=merged_df['bucket_start'], y=merged_df['Close'],
                                            mode='lines', name='Preço', yaxis='y2', line=dict(color='#ff7f0e')))

                    fig.update_layout(
                        title=f'Probabilidade de Subida vs Preço para {selected_entity}',
                        xaxis=dict(title='Data'),
                        yaxis=dict(title='Probabilidade', tickfont=dict(color='#1f77b4'), tickformat='.1%'),
                        yaxis2=dict(title='Preço', tickfont=dict(color='#ff7f0e'),
                                    overlaying='y', side='right'),
                        template='plotly_white'
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # Correlation
                    corr = merged_df[['probability', 'Close']].corr().iloc[0,1]
                    st.metric("Correlação Probabilidade-Preço", f"{corr:.3f}")
    
    # Correlation matrix
    if len(selected_entities) > 1 and 'probability' in filtered_df.columns:
        pivot_df = filtered_df.pivot(index='bucket_start', columns='ticker', values='probability')
        corr_matrix = pivot_df.corr()

        fig = px.imshow(corr_matrix, text_auto=True, title='Matriz de Correlação da Probabilidade de Subida',
                        template='plotly_white', color_continuous_scale='RdBu_r')
        st.plotly_chart(fig, use_container_width=True)

with tab5:
    st.header("✅ Validação do Modelo")
    st.markdown("Compare as probabilidades previstas com os movimentos reais de preço.")
    
    # Select stock for validation
    validation_stocks = [e for e in entities if e.endswith('.SA')]
    if validation_stocks:
        val_ticker = st.selectbox("Selecionar Ativo para Validação", validation_stocks, key='val_ticker')
        
        if val_ticker:
            # Load price data
            val_price_df = load_price_data(val_ticker, period='1y')
            val_sent_df = sentiment_df[sentiment_df['ticker'] == val_ticker].copy()
            
            if not val_price_df.empty and not val_sent_df.empty:
                # Merge data
                val_merged = pd.merge(
                    val_sent_df, 
                    val_price_df, 
                    left_on='bucket_start', 
                    right_on='Date', 
                    how='inner'
                )
                
                if not val_merged.empty and 'probability' in val_merged.columns:
                    # Calculate returns
                    val_merged = val_merged.sort_values('bucket_start')
                    val_merged['return_1w'] = val_merged['Close'].pct_change()
                    val_merged['actual_up'] = (val_merged['return_1w'].shift(-1) > 0).astype(int)
                    
                    # Main comparison chart
                    st.subheader("📊 Probabilidade vs Retorno Real")
                    
                    fig = go.Figure()
                    
                    # Probability line
                    fig.add_trace(go.Scatter(
                        x=val_merged['bucket_start'], 
                        y=val_merged['probability'],
                        mode='lines+markers', 
                        name='Prob. Subida (Previsto)',
                        line=dict(color='#2E86AB', width=2),
                        marker=dict(size=6)
                    ))
                    
                    # Actual up/down markers
                    up_mask = val_merged['actual_up'] == 1
                    fig.add_trace(go.Scatter(
                        x=val_merged.loc[up_mask, 'bucket_start'],
                        y=[1.05] * up_mask.sum(),
                        mode='markers',
                        name='Subiu (Real)',
                        marker=dict(color='green', size=10, symbol='triangle-up')
                    ))
                    
                    down_mask = val_merged['actual_up'] == 0
                    fig.add_trace(go.Scatter(
                        x=val_merged.loc[down_mask, 'bucket_start'],
                        y=[-0.05] * down_mask.sum(),
                        mode='markers',
                        name='Desceu (Real)',
                        marker=dict(color='red', size=10, symbol='triangle-down')
                    ))
                    
                    # Threshold lines
                    fig.add_hline(y=0.62, line_dash='dash', line_color='green', 
                                  annotation_text='Threshold Long (62%)')
                    fig.add_hline(y=0.38, line_dash='dash', line_color='red',
                                  annotation_text='Threshold Short (38%)')
                    
                    fig.update_layout(
                        title=f'Validação do Modelo para {val_ticker}',
                        xaxis_title='Data',
                        yaxis_title='Probabilidade',
                        yaxis_tickformat='.0%',
                        template='plotly_white',
                        height=500,
                        showlegend=True,
                        legend=dict(orientation='h', yanchor='bottom', y=1.02)
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Metrics
                    st.subheader("📈 Métricas de Validação")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    # Calculate accuracy
                    val_clean = val_merged.dropna(subset=['actual_up'])
                    if not val_clean.empty:
                        predicted_up = (val_clean['probability'] > 0.5).astype(int)
                        accuracy = (predicted_up == val_clean['actual_up']).mean()
                        
                        # Precision when predicting up
                        high_prob = val_clean['probability'] > 0.62
                        if high_prob.sum() > 0:
                            precision_high = val_clean.loc[high_prob, 'actual_up'].mean()
                        else:
                            precision_high = 0
                        
                        # Correlation
                        corr = val_clean[['probability', 'actual_up']].corr().iloc[0,1]
                        
                        with col1:
                            st.metric("Acurácia Geral", f"{accuracy:.1%}")
                        with col2:
                            st.metric("Precisão (prob > 62%)", f"{precision_high:.1%}")
                        with col3:
                            st.metric("Correlação", f"{corr:.3f}")
                        with col4:
                            st.metric("Amostras", f"{len(val_clean)}")
                    
                    # Rolling correlation chart
                    st.subheader("📉 Correlação Rolling (30 dias)")
                    
                    if len(val_merged) > 30:
                        val_merged['rolling_corr'] = val_merged['probability'].rolling(window=4).corr(
                            val_merged['Close'].pct_change().shift(-1)
                        )
                        
                        fig_corr = px.line(
                            val_merged, x='bucket_start', y='rolling_corr',
                            title='Correlação Rolling: Probabilidade vs Retorno Futuro',
                            template='plotly_white'
                        )
                        fig_corr.add_hline(y=0, line_dash='dash', line_color='gray')
                        fig_corr.update_layout(height=300, yaxis_title='Correlação')
                        st.plotly_chart(fig_corr, use_container_width=True)
                else:
                    st.warning("Dados insuficientes para validação.")
            else:
                st.warning("Não foi possível carregar dados de preço ou sentimento.")
    else:
        st.info("Nenhuma ação (.SA) disponível para validação.")

with tab4:
    st.header("Dados Brutos")

    # Export button
    if not filtered_df.empty:
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="📥 Baixar Dados Filtrados como CSV",
            data=csv,
            file_name='sentiment_data.csv',
            mime='text/csv'
        )

    st.dataframe(filtered_df, use_container_width=True)

    # Data summary
    st.subheader("Resumo dos Dados")
    st.write(filtered_df.describe())