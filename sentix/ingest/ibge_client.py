"""
IBGE Client - Integração com a API do IBGE.

Este módulo consulta dados econômicos do IBGE via SIDRA API,
incluindo IPCA, PIB, Desemprego (PNAD) e outros indicadores.

API Docs: https://servicodados.ibge.gov.br/api/docs
"""

from typing import Dict, List, Any, Optional
import requests
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Base URLs
SIDRA_API = "https://servicodados.ibge.gov.br/api/v3/agregados"
IBGE_API = "https://servicodados.ibge.gov.br/api/v1"

# Códigos de tabelas SIDRA
TABELAS = {
    'IPCA': 1737,           # IPCA - Variação mensal
    'IPCA_ACUM_12M': 7060,  # IPCA acumulado 12 meses
    'PIB': 5932,            # PIB Trimestral
    'DESEMPREGO': 4099,     # PNAD - Taxa de desocupação
    'PRODUCAO_INDUSTRIAL': 3653  # Produção Industrial
}


class IBGEClient:
    """
    Cliente para APIs do IBGE.
    
    Permite consultar dados econômicos como IPCA, PIB,
    desemprego e produção industrial.
    
    Example:
        >>> client = IBGEClient()
        >>> ipca = client.get_ipca_monthly(last_n=12)
        >>> print(ipca)
    """
    
    def __init__(self, timeout: int = 30):
        """
        Inicializa o cliente IBGE.
        
        Args:
            timeout: Timeout para requests em segundos.
        """
        self.timeout = timeout
        self.session = requests.Session()
    
    def get_ipca_monthly(self, last_n: int = 12) -> pd.DataFrame:
        """
        Obtém IPCA mensal.
        
        Args:
            last_n: Número de meses para buscar.
            
        Returns:
            DataFrame com IPCA mensal.
        """
        # SIDRA format: /t/{tabela}/n1/all/v/all/p/last%20{n}
        url = f"{SIDRA_API}/{TABELAS['IPCA']}/periodos/-{last_n}/variaveis/63|69|2265?localidades=N1[all]"
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            records = []
            for item in data:
                variable = item.get('variavel', '')
                for serie in item.get('resultados', []):
                    for periodo in serie.get('series', []):
                        for key, value in periodo.get('serie', {}).items():
                            records.append({
                                'period': key,
                                'variable': variable,
                                'value': float(value) if value and value != '-' else None
                            })
            
            df = pd.DataFrame(records)
            
            if not df.empty:
                # Pivot para ter variáveis como colunas
                df_pivot = df.pivot(index='period', columns='variable', values='value')
                df_pivot = df_pivot.reset_index()
                df_pivot.columns.name = None
                
                # Converte período para datetime
                df_pivot['date'] = pd.to_datetime(df_pivot['period'], format='%Y%m')
                
                logger.info(f"Fetched {len(df_pivot)} IPCA records from IBGE")
                return df_pivot
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"Error fetching IPCA from IBGE: {e}")
            return pd.DataFrame()
    
    def get_pib_quarterly(self, last_n: int = 8) -> pd.DataFrame:
        """
        Obtém PIB trimestral.
        
        Args:
            last_n: Número de trimestres para buscar.
            
        Returns:
            DataFrame com PIB trimestral.
        """
        # PIB - Taxa de variação (série encadeada)
        url = f"{SIDRA_API}/{TABELAS['PIB']}/periodos/-{last_n}/variaveis/6561?localidades=N1[all]"
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            records = []
            for item in data:
                for serie in item.get('resultados', []):
                    for periodo in serie.get('series', []):
                        for key, value in periodo.get('serie', {}).items():
                            records.append({
                                'period': key,
                                'pib_growth': float(value) if value and value != '-' else None
                            })
            
            df = pd.DataFrame(records)
            
            if not df.empty:
                # Converte período trimestral (ex: 202401) para data
                def period_to_date(p):
                    year = int(str(p)[:4])
                    quarter = int(str(p)[4:])
                    month = (quarter - 1) * 3 + 1
                    return datetime(year, month, 1)
                
                df['date'] = df['period'].apply(period_to_date)
                df = df.sort_values('date')
                
                logger.info(f"Fetched {len(df)} PIB records from IBGE")
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching PIB from IBGE: {e}")
            return pd.DataFrame()
    
    def get_unemployment_rate(self, last_n: int = 12) -> pd.DataFrame:
        """
        Obtém taxa de desemprego (PNAD).
        
        Args:
            last_n: Número de trimestres para buscar.
            
        Returns:
            DataFrame com taxa de desemprego.
        """
        # PNAD Contínua - Taxa de desocupação
        url = f"{SIDRA_API}/{TABELAS['DESEMPREGO']}/periodos/-{last_n}/variaveis/4099?localidades=N1[all]"
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            records = []
            for item in data:
                for serie in item.get('resultados', []):
                    for periodo in serie.get('series', []):
                        for key, value in periodo.get('serie', {}).items():
                            records.append({
                                'period': key,
                                'unemployment_rate': float(value) if value and value not in ['-', '...'] else None
                            })
            
            df = pd.DataFrame(records)
            
            if not df.empty:
                df['date'] = pd.to_datetime(df['period'], format='%Y%m', errors='coerce')
                df = df.dropna(subset=['date']).sort_values('date')
                
                logger.info(f"Fetched {len(df)} unemployment records from IBGE")
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching unemployment from IBGE: {e}")
            return pd.DataFrame()
    
    def get_industrial_production(self, last_n: int = 12) -> pd.DataFrame:
        """
        Obtém índice de produção industrial.
        
        Args:
            last_n: Número de meses para buscar.
            
        Returns:
            DataFrame com produção industrial.
        """
        url = f"{SIDRA_API}/{TABELAS['PRODUCAO_INDUSTRIAL']}/periodos/-{last_n}/variaveis/3135?localidades=N1[all]"
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            records = []
            for item in data:
                for serie in item.get('resultados', []):
                    for periodo in serie.get('series', []):
                        for key, value in periodo.get('serie', {}).items():
                            records.append({
                                'period': key,
                                'industrial_production': float(value) if value and value != '-' else None
                            })
            
            df = pd.DataFrame(records)
            
            if not df.empty:
                df['date'] = pd.to_datetime(df['period'], format='%Y%m', errors='coerce')
                df = df.dropna(subset=['date']).sort_values('date')
                
                logger.info(f"Fetched {len(df)} industrial production records from IBGE")
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching industrial production from IBGE: {e}")
            return pd.DataFrame()
    
    def get_all_indicators(self, months: int = 12) -> Dict[str, pd.DataFrame]:
        """
        Obtém todos os indicadores disponíveis.
        
        Args:
            months: Número de períodos para buscar.
            
        Returns:
            Dicionário com DataFrames para cada indicador.
        """
        return {
            'ipca': self.get_ipca_monthly(months),
            'pib': self.get_pib_quarterly(months // 3),
            'unemployment': self.get_unemployment_rate(months),
            'industrial': self.get_industrial_production(months)
        }
    
    def get_economic_summary(self) -> Dict[str, Any]:
        """
        Obtém resumo econômico com últimos valores.
        
        Returns:
            Dicionário com resumo.
        """
        summary = {}
        
        # IPCA
        ipca = self.get_ipca_monthly(last_n=1)
        if not ipca.empty:
            summary['ipca'] = {
                'period': str(ipca.iloc[-1]['date'].date()) if 'date' in ipca.columns else 'N/A',
                'monthly': ipca.iloc[-1].get('IPCA - Variação mensal', 'N/A')
            }
        
        # PIB
        pib = self.get_pib_quarterly(last_n=1)
        if not pib.empty:
            summary['pib'] = {
                'period': str(pib.iloc[-1]['date'].date()) if 'date' in pib.columns else 'N/A',
                'growth': pib.iloc[-1].get('pib_growth', 'N/A')
            }
        
        # Desemprego
        unemployment = self.get_unemployment_rate(last_n=1)
        if not unemployment.empty:
            summary['unemployment'] = {
                'period': str(unemployment.iloc[-1]['date'].date()) if 'date' in unemployment.columns else 'N/A',
                'rate': unemployment.iloc[-1].get('unemployment_rate', 'N/A')
            }
        
        return summary


def fetch_ibge_data(indicators: List[str] = None, months: int = 12) -> pd.DataFrame:
    """
    Função de conveniência para buscar dados IBGE.
    
    Args:
        indicators: Lista de indicadores ('ipca', 'pib', 'unemployment', 'industrial').
                   Se None, busca todos.
        months: Número de meses/períodos.
        
    Returns:
        DataFrame consolidado.
    """
    client = IBGEClient()
    
    if indicators is None:
        indicators = ['ipca', 'pib', 'unemployment', 'industrial']
    
    all_data = []
    
    for ind in indicators:
        ind = ind.lower()
        
        if ind == 'ipca':
            df = client.get_ipca_monthly(months)
            if not df.empty and 'date' in df.columns:
                df['indicator'] = 'IPCA'
                all_data.append(df[['date', 'indicator']].copy())
                
        elif ind == 'pib':
            df = client.get_pib_quarterly(months // 3)
            if not df.empty and 'date' in df.columns:
                df['indicator'] = 'PIB'
                df['value'] = df['pib_growth']
                all_data.append(df[['date', 'indicator', 'value']].copy())
                
        elif ind == 'unemployment':
            df = client.get_unemployment_rate(months)
            if not df.empty and 'date' in df.columns:
                df['indicator'] = 'DESEMPREGO'
                df['value'] = df['unemployment_rate']
                all_data.append(df[['date', 'indicator', 'value']].copy())
                
        elif ind == 'industrial':
            df = client.get_industrial_production(months)
            if not df.empty and 'date' in df.columns:
                df['indicator'] = 'PRODUCAO_INDUSTRIAL'
                df['value'] = df['industrial_production']
                all_data.append(df[['date', 'indicator', 'value']].copy())
    
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return pd.DataFrame()


if __name__ == "__main__":
    # Test the client
    logging.basicConfig(level=logging.INFO)
    
    client = IBGEClient()
    
    print("\n=== IPCA Monthly ===")
    ipca = client.get_ipca_monthly(last_n=6)
    print(ipca)
    
    print("\n=== PIB Quarterly ===")
    pib = client.get_pib_quarterly(last_n=4)
    print(pib)
    
    print("\n=== Economic Summary ===")
    summary = client.get_economic_summary()
    print(summary)
