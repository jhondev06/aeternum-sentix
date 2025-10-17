#!/usr/bin/env python3
"""
Script de inicialização para deploy: gera dados demo e treina o modelo automaticamente.
"""

import os
import sys
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("Iniciando configuração do modelo Sentix...")

        # Criar diretórios necessários
        os.makedirs('data', exist_ok=True)
        os.makedirs('outputs', exist_ok=True)

        # 1. Gerar dados demo
        logger.info("Gerando dados demo...")
        from demo_data_generator import DemoDataGenerator

        generator = DemoDataGenerator()
        generator.generate_demo_data(num_articles=300, days_back=90)
        logger.info("Dados demo gerados com sucesso")

        # 2. Treinar modelo
        logger.info("Treinando modelo...")
        from models.prob_model import ProbModel

        ProbModel.train_and_save('data/training_set.csv', 'outputs/prob_model.pkl')
        logger.info("Modelo treinado e salvo com sucesso")

        # 3. Verificar se os arquivos foram criados
        if os.path.exists('data/sentiment_bars.csv') and os.path.exists('outputs/prob_model.pkl'):
            logger.info("Configuração concluída com sucesso!")
            return True
        else:
            logger.error("Arquivos necessários não foram criados")
            return False

    except Exception as e:
        logger.error(f"Erro durante inicialização: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)