#!/usr/bin/env python3
"""
Generate additional articles for IPCA and PIB to add to existing data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import uuid

def generate_additional_articles(num_articles_per_ticker=50, days_back=30):
    """Generate sample articles for IPCA and PIB"""

    # Article templates for economic indicators
    article_templates = [
        # Positive for inflation/economy
        {
            "title": "IPCA registra deflação de {}% em {}, melhor resultado em anos",
            "body": "O Índice Nacional de Preços ao Consumidor Amplo (IPCA) apresentou deflação de {}% no mês de {}, o melhor resultado desde {}. Economistas atribuem a queda aos efeitos da política monetária e à estabilização dos preços de commodities.",
            "sentiment": "positive"
        },
        {
            "title": "PIB cresce {}% no trimestre, superando expectativas",
            "body": "O Produto Interno Bruto (PIB) brasileiro registrou crescimento de {}% no último trimestre, acima das projeções de mercado. O resultado foi impulsionado pelos setores de serviços e indústria, indicando recuperação econômica.",
            "sentiment": "positive"
        },
        {
            "title": "Inflação controlada impulsiona confiança do consumidor",
            "body": "Com a inflação sob controle, a confiança do consumidor brasileiro atingiu o maior nível em {} meses. O IPCA de {}% sinaliza estabilidade econômica e abre espaço para redução da taxa Selic.",
            "sentiment": "positive"
        },
        {
            "title": "Economia brasileira acelera com PIB em expansão",
            "body": "O PIB brasileiro mostrou sinais de aceleração, com crescimento de {}% no período. Analistas destacam a contribuição dos investimentos e do consumo interno para o desempenho positivo.",
            "sentiment": "positive"
        },

        # Negative for inflation/economy
        {
            "title": "IPCA acelera para {}%, pressionando política monetária",
            "body": "O Índice Nacional de Preços ao Consumidor Amplo (IPCA) registrou inflação de {}% em {}, acima das expectativas. O resultado aumenta a pressão sobre o Banco Central para manter ou elevar a taxa Selic.",
            "sentiment": "negative"
        },
        {
            "title": "PIB recua {}% no trimestre, economia em desaceleração",
            "body": "O Produto Interno Bruto (PIB) brasileiro apresentou contração de {}% no último trimestre, sinalizando desaceleração econômica. Os setores de indústria e agricultura foram os mais afetados.",
            "sentiment": "negative"
        },
        {
            "title": "Inflação persistente preocupa economistas",
            "body": "A inflação medida pelo IPCA permanece elevada em {}%, preocupando economistas e investidores. O cenário desafiador pode impactar as decisões de investimento e consumo no país.",
            "sentiment": "negative"
        },
        {
            "title": "Crescimento econômico abaixo do esperado",
            "body": "O PIB brasileiro cresceu apenas {}% no trimestre, abaixo das projeções de mercado. Fatores como alta inflação e juros elevados contribuem para o desempenho abaixo do potencial.",
            "sentiment": "negative"
        },

        # Neutral
        {
            "title": "IPCA fica em {}%, dentro da meta do Banco Central",
            "body": "O Índice Nacional de Preços ao Consumidor Amplo (IPCA) registrou inflação de {}% em {}, dentro do centro da meta estabelecida pelo Banco Central. O resultado mantém a política monetária em compasso de espera.",
            "sentiment": "neutral"
        },
        {
            "title": "PIB mantém trajetória de crescimento moderado",
            "body": "O Produto Interno Bruto (PIB) brasileiro apresentou crescimento de {}% no trimestre, mantendo a trajetória de recuperação gradual. O desempenho é considerado adequado pelas autoridades econômicas.",
            "sentiment": "neutral"
        }
    ]

    # Entity names
    entities = {
        "IPCA": ["inflação brasileira", "IPCA", "índice de preços"],
        "PIB": ["economia brasileira", "PIB", "Produto Interno Bruto"]
    }

    articles = []
    base_date = datetime.now() - timedelta(days=days_back)

    for ticker in ["IPCA", "PIB"]:
        entity_names = entities[ticker]

        for i in range(num_articles_per_ticker):
            # Random template
            template = np.random.choice(article_templates)

            # Generate article
            published_at = base_date + timedelta(
                days=np.random.randint(0, days_back),
                hours=np.random.randint(0, 24),
                minutes=np.random.randint(0, 60)
            )

            # Fill template with random values
            entity_name = np.random.choice(entity_names)

            if ticker == "IPCA":
                rate = np.random.uniform(0.1, 1.2)  # inflation rate
                month = np.random.choice(["janeiro", "fevereiro", "março", "abril", "maio", "junho"])
                title_placeholders = template["title"].count("{}")
                body_placeholders = template["body"].count("{}")

                if title_placeholders == 2:
                    title = template["title"].format(f"{rate:.1f}", month)
                elif title_placeholders == 1:
                    title = template["title"].format(f"{rate:.1f}")
                else:
                    title = template["title"]

                if body_placeholders == 4:
                    body = template["body"].format(f"{rate:.1f}", f"{rate:.1f}", month, "2020")
                elif body_placeholders == 1:
                    body = template["body"].format(f"{rate:.1f}")
                else:
                    body = template["body"]
            else:  # PIB
                growth = np.random.uniform(-1.0, 2.0)  # GDP growth
                title_placeholders = template["title"].count("{}")
                body_placeholders = template["body"].count("{}")

                if title_placeholders == 1:
                    title = template["title"].format(f"{growth:.1f}")
                else:
                    title = template["title"]

                if body_placeholders == 2:
                    body = template["body"].format(f"{growth:.1f}", f"{growth:.1f}")
                elif body_placeholders == 1:
                    body = template["body"].format(f"{growth:.1f}")
                else:
                    body = template["body"]

            article = {
                "id": str(uuid.uuid4().hex),
                "ticker": ticker,
                "published_at": published_at.isoformat() + "Z",
                "title": title,
                "body": body,
                "url": f"https://demo-economy.com/article/{ticker}_{i}",
                "lang": "pt",
                "source": "demo-economy.com"
            }

            articles.append(article)

    return pd.DataFrame(articles)

if __name__ == "__main__":
    # Generate articles
    new_articles = generate_additional_articles(num_articles_per_ticker=30, days_back=60)
    print(f"Generated {len(new_articles)} new articles")

    # Load existing articles
    existing_df = pd.read_csv('data/articles_raw.csv')

    # Append new articles
    combined_df = pd.concat([existing_df, new_articles], ignore_index=True)

    # Save back
    combined_df.to_csv('data/articles_raw.csv', index=False)
    print(f"Total articles now: {len(combined_df)}")
    print("Articles saved to data/articles_raw.csv")