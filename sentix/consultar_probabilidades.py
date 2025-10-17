#!/usr/bin/env python3
"""
Script simplificado para consultar probabilidades de subida/descida de ações
usando análise de sentimento com FinBERT.
"""

import pandas as pd
import yaml
import os
from models.prob_model import ProbModel

def carregar_config():
    """Carrega a configuração do sistema."""
    with open('config.yml', 'r') as f:
        return yaml.safe_load(f)

def treinar_ou_carregar_modelo():
    """Treina ou carrega o modelo de probabilidade."""
    model_path = 'outputs/prob_model.pkl'

    if os.path.exists(model_path):
        print("Carregando modelo existente...")
        model = ProbModel.load(model_path)
    else:
        print("Modelo não encontrado. Treinando novo modelo com dados demo...")
        if not os.path.exists('data/training_set.csv'):
            print("Dados de treinamento não encontrados. Execute demo_data_generator.py primeiro.")
            return None

        ProbModel.train_and_save('data/training_set.csv', model_path)
        model = ProbModel.load(model_path)
        print("Modelo treinado e salvo.")

    return model

def obter_tickers_disponiveis():
    """Retorna lista de tickers disponíveis nos dados."""
    if not os.path.exists('data/sentiment_bars.csv'):
        print("Dados de sentiment_bars não encontrados.")
        return []

    df = pd.read_csv('data/sentiment_bars.csv')
    return sorted(df['ticker'].unique())

def obter_features_recentes(ticker):
    """Obtém as features mais recentes para um ticker."""
    if not os.path.exists('data/sentiment_bars.csv'):
        return None

    df = pd.read_csv('data/sentiment_bars.csv')
    df['bucket_start'] = pd.to_datetime(df['bucket_start'])

    # Filtrar por ticker e pegar o mais recente
    ticker_data = df[df['ticker'] == ticker]
    if ticker_data.empty:
        return None

    recent_data = ticker_data.sort_values('bucket_start').iloc[-1]

    # Selecionar apenas as features numéricas
    features = ['mean_sent', 'std_sent', 'min_sent', 'max_sent', 'count', 'unc_mean', 'time_decay_mean']
    feature_values = recent_data[features].fillna(0)

    return pd.DataFrame([feature_values])

def interpretar_probabilidade(probabilidade):
    """Interpreta a probabilidade de subida."""
    if probabilidade > 0.6:
        return "ALTA probabilidade de SUBIDA"
    elif probabilidade > 0.5:
        return "Moderada probabilidade de SUBIDA"
    elif probabilidade > 0.4:
        return "Moderada probabilidade de DESCIDA"
    else:
        return "ALTA probabilidade de DESCIDA"

def consultar_ticker(model, ticker):
    """Consulta probabilidade para um ticker específico."""
    # Obter features
    features_df = obter_features_recentes(ticker)
    if features_df is None or features_df.empty:
        print(f"Nenhum dado recente encontrado para {ticker}.")
        return

    # Prever probabilidade
    try:
        prob = model.predict_proba(features_df)[0]
        interpretacao = interpretar_probabilidade(prob)

        print(f"\n{'='*50}")
        print(f"TICKER: {ticker}")
        print(f"Probabilidade de subida: {prob:.1%}")
        print(f"Interpretação: {interpretacao}")
        print(f"{'='*50}\n")

    except Exception as e:
        print(f"Erro ao calcular probabilidade para {ticker}: {e}")

def modo_demo(model, tickers):
    """Modo demonstração - consulta alguns tickers automaticamente."""
    print("\nMODO DEMO - Consultando probabilidades para alguns tickers:")
    print("-" * 60)

    # Selecionar alguns tickers para demo
    demo_tickers = tickers[:5]  # primeiros 5

    for ticker in demo_tickers:
        consultar_ticker(model, ticker)

def main():
    import sys

    print("=" * 60)
    print("CONSULTOR DE PROBABILIDADES DE AÇÕES - SENTIX")
    print("=" * 60)
    print("Este script usa análise de sentimento para estimar")
    print("probabilidades de subida ou descida de ações.")
    print()

    # Verificar se foi passado argumento de ticker
    if len(sys.argv) > 1:
        ticker_especifico = sys.argv[1]
        print(f"Consultando ticker específico: {ticker_especifico}")
    else:
        ticker_especifico = None

    # Carregar configuração
    try:
        config = carregar_config()
    except Exception as e:
        print(f"Erro ao carregar configuração: {e}")
        return

    # Treinar/carregar modelo
    model = treinar_ou_carregar_modelo()
    if model is None:
        return

    # Obter tickers disponíveis
    tickers = obter_tickers_disponiveis()
    if not tickers:
        print("Nenhum ticker encontrado nos dados.")
        return

    # Se ticker específico foi passado
    if ticker_especifico:
        if ticker_especifico in tickers:
            consultar_ticker(model, ticker_especifico)
        else:
            print(f"Ticker {ticker_especifico} não encontrado. Tickers disponíveis: {', '.join(tickers)}")
        return

    # Verificar se há entrada disponível (modo interativo)
    try:
        # No Windows, tentar detectar se há entrada pendente não é confiável
        # Vamos assumir modo demo por padrão, e interativo apenas se especificado
        if '--interactive' in sys.argv or len(sys.argv) > 1 and sys.argv[1] != '--demo':
            # Modo interativo
            print(f"Tickers disponíveis ({len(tickers)}):")
            for i, ticker in enumerate(tickers, 1):
                print(f"{i:2d}. {ticker}")
            print()

            # Loop principal
            while True:
                try:
                    escolha = input("Digite o número do ticker (ou 'q' para sair): ").strip()

                    if escolha.lower() == 'q':
                        print("Até logo!")
                        break

                    idx = int(escolha) - 1
                    if 0 <= idx < len(tickers):
                        ticker = tickers[idx]
                        consultar_ticker(model, ticker)
                    else:
                        print("Número inválido. Tente novamente.")
                        continue

                except (ValueError, EOFError):
                    print("Entrada inválida. Digite um número ou 'q'.")
                    continue
        else:
            # Modo demo por padrão
            modo_demo(model, tickers)

    except Exception:
        # Em caso de erro, executar modo demo
        modo_demo(model, tickers)

if __name__ == "__main__":
    main()