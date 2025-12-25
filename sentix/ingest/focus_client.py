"""
Focus Client - Integração com a API Focus do Banco Central do Brasil.

Este módulo faz a consulta das expectativas de mercado para indicadores
econômicos como IPCA, SELIC, PIB e Câmbio.

API Docs: https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/documentacao
"""

from typing import Dict, List, Any, Optional
import requests
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Base URL da API Focus
FOCUS_API_BASE = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata"

# Indicadores disponíveis
INDICADORES = {
    'IPCA': 'ExpectativasMercadoInflacao12Meses',
    'SELIC': 'ExpectativasMercadoSelic',
    'PIB': 'ExpectativasMercadoAnuais',
    'CAMBIO': 'ExpectativasMercadoAnuais'
}


class FocusClient:
    """
    Cliente para a API Focus do Banco Central.
    
    O relatório Focus é publicado semanalmente e contém as expectativas
    de mercado para os principais indicadores econômicos.
    
    Example:
        >>> client = FocusClient()
        >>> ipca = client.get_ipca_expectations(last_n_weeks=4)
        >>> print(ipca.head())
    """
    
    def __init__(self, timeout: int = 30):
        """
        Inicializa o cliente Focus.
        
        Args:
            timeout: Timeout para requests em segundos.
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json'
        })
    
    def get_ipca_expectations(
        self,
        last_n_weeks: int = 12,
        smoothed: bool = True
    ) -> pd.DataFrame:
        """
        Obtém expectativas de IPCA (12 meses).
        
        Args:
            last_n_weeks: Número de semanas para buscar.
            smoothed: Se True, retorna média suavizada.
            
        Returns:
            DataFrame com colunas: date, ipca_median, ipca_mean, ipca_min, ipca_max
        """
        endpoint = f"{FOCUS_API_BASE}/ExpectativasMercadoInflacao12Meses"
        
        start_date = (datetime.now() - timedelta(weeks=last_n_weeks)).strftime('%Y-%m-%d')
        
        params = {
            '$filter': f"Indicador eq 'IPCA' and Data ge '{start_date}'",
            '$orderby': 'Data desc',
            '$format': 'json',
            '$select': 'Data,Mediana,Media,Minimo,Maximo'
        }
        
        try:
            response = self.session.get(endpoint, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            if 'value' not in data:
                return pd.DataFrame()
            
            df = pd.DataFrame(data['value'])
            df = df.rename(columns={
                'Data': 'date',
                'Mediana': 'ipca_median',
                'Media': 'ipca_mean',
                'Minimo': 'ipca_min',
                'Maximo': 'ipca_max'
            })
            df['date'] = pd.to_datetime(df['date'])
            
            logger.info(f"Fetched {len(df)} IPCA expectations from Focus")
            return df
            
        except requests.RequestException as e:
            logger.error(f"Error fetching IPCA expectations: {e}")
            return pd.DataFrame()
    
    def get_selic_expectations(
        self,
        last_n_weeks: int = 12,
        reuniao: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Obtém expectativas de SELIC.
        
        Args:
            last_n_weeks: Número de semanas para buscar.
            reuniao: Filtrar por reunião específica do COPOM (ex: 'R1/2024').
            
        Returns:
            DataFrame com expectativas de SELIC.
        """
        endpoint = f"{FOCUS_API_BASE}/ExpectativasMercadoSelic"
        
        start_date = (datetime.now() - timedelta(weeks=last_n_weeks)).strftime('%Y-%m-%d')
        
        filter_str = f"Data ge '{start_date}'"
        if reuniao:
            filter_str += f" and Reuniao eq '{reuniao}'"
        
        params = {
            '$filter': filter_str,
            '$orderby': 'Data desc',
            '$format': 'json',
            '$select': 'Data,Reuniao,Mediana,Media,Minimo,Maximo'
        }
        
        try:
            response = self.session.get(endpoint, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            if 'value' not in data:
                return pd.DataFrame()
            
            df = pd.DataFrame(data['value'])
            df = df.rename(columns={
                'Data': 'date',
                'Reuniao': 'meeting',
                'Mediana': 'selic_median',
                'Media': 'selic_mean',
                'Minimo': 'selic_min',
                'Maximo': 'selic_max'
            })
            df['date'] = pd.to_datetime(df['date'])
            
            logger.info(f"Fetched {len(df)} SELIC expectations from Focus")
            return df
            
        except requests.RequestException as e:
            logger.error(f"Error fetching SELIC expectations: {e}")
            return pd.DataFrame()
    
    def get_pib_expectations(
        self,
        year: Optional[int] = None,
        last_n_weeks: int = 12
    ) -> pd.DataFrame:
        """
        Obtém expectativas de PIB.
        
        Args:
            year: Ano de referência (ex: 2024). Se None, usa ano atual e próximo.
            last_n_weeks: Número de semanas para buscar.
            
        Returns:
            DataFrame com expectativas de PIB.
        """
        endpoint = f"{FOCUS_API_BASE}/ExpectativasMercadoAnuais"
        
        start_date = (datetime.now() - timedelta(weeks=last_n_weeks)).strftime('%Y-%m-%d')
        
        if year is None:
            year = datetime.now().year
        
        filter_str = f"Indicador eq 'PIB Total' and Data ge '{start_date}' and DataReferencia eq '{year}'"
        
        params = {
            '$filter': filter_str,
            '$orderby': 'Data desc',
            '$format': 'json',
            '$select': 'Data,DataReferencia,Mediana,Media,Minimo,Maximo'
        }
        
        try:
            response = self.session.get(endpoint, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            if 'value' not in data:
                return pd.DataFrame()
            
            df = pd.DataFrame(data['value'])
            df = df.rename(columns={
                'Data': 'date',
                'DataReferencia': 'reference_year',
                'Mediana': 'pib_median',
                'Media': 'pib_mean',
                'Minimo': 'pib_min',
                'Maximo': 'pib_max'
            })
            df['date'] = pd.to_datetime(df['date'])
            
            logger.info(f"Fetched {len(df)} PIB expectations from Focus")
            return df
            
        except requests.RequestException as e:
            logger.error(f"Error fetching PIB expectations: {e}")
            return pd.DataFrame()
    
    def get_cambio_expectations(
        self,
        year: Optional[int] = None,
        last_n_weeks: int = 12
    ) -> pd.DataFrame:
        """
        Obtém expectativas de câmbio (USD/BRL).
        
        Args:
            year: Ano de referência.
            last_n_weeks: Número de semanas para buscar.
            
        Returns:
            DataFrame com expectativas de câmbio.
        """
        endpoint = f"{FOCUS_API_BASE}/ExpectativasMercadoAnuais"
        
        start_date = (datetime.now() - timedelta(weeks=last_n_weeks)).strftime('%Y-%m-%d')
        
        if year is None:
            year = datetime.now().year
        
        filter_str = f"Indicador eq 'Câmbio' and Data ge '{start_date}' and DataReferencia eq '{year}'"
        
        params = {
            '$filter': filter_str,
            '$orderby': 'Data desc',
            '$format': 'json',
            '$select': 'Data,DataReferencia,Mediana,Media,Minimo,Maximo'
        }
        
        try:
            response = self.session.get(endpoint, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            if 'value' not in data:
                return pd.DataFrame()
            
            df = pd.DataFrame(data['value'])
            df = df.rename(columns={
                'Data': 'date',
                'DataReferencia': 'reference_year',
                'Mediana': 'cambio_median',
                'Media': 'cambio_mean',
                'Minimo': 'cambio_min',
                'Maximo': 'cambio_max'
            })
            df['date'] = pd.to_datetime(df['date'])
            
            logger.info(f"Fetched {len(df)} Cambio expectations from Focus")
            return df
            
        except requests.RequestException as e:
            logger.error(f"Error fetching Cambio expectations: {e}")
            return pd.DataFrame()
    
    def get_all_expectations(self, last_n_weeks: int = 12) -> Dict[str, pd.DataFrame]:
        """
        Obtém todas as expectativas disponíveis.
        
        Args:
            last_n_weeks: Número de semanas para buscar.
            
        Returns:
            Dicionário com DataFrames para cada indicador.
        """
        return {
            'ipca': self.get_ipca_expectations(last_n_weeks),
            'selic': self.get_selic_expectations(last_n_weeks),
            'pib': self.get_pib_expectations(last_n_weeks=last_n_weeks),
            'cambio': self.get_cambio_expectations(last_n_weeks=last_n_weeks)
        }
    
    def get_latest_summary(self) -> Dict[str, Any]:
        """
        Obtém resumo das últimas expectativas.
        
        Retorna a mediana mais recente de cada indicador.
        
        Returns:
            Dicionário com valores mais recentes.
        """
        summary = {}
        
        # IPCA
        ipca = self.get_ipca_expectations(last_n_weeks=2)
        if not ipca.empty:
            summary['ipca_12m'] = {
                'value': ipca.iloc[0]['ipca_median'],
                'date': str(ipca.iloc[0]['date'].date())
            }
        
        # SELIC
        selic = self.get_selic_expectations(last_n_weeks=2)
        if not selic.empty:
            summary['selic'] = {
                'value': selic.iloc[0]['selic_median'],
                'date': str(selic.iloc[0]['date'].date()),
                'meeting': selic.iloc[0].get('meeting', 'N/A')
            }
        
        # PIB
        pib = self.get_pib_expectations(last_n_weeks=2)
        if not pib.empty:
            summary['pib'] = {
                'value': pib.iloc[0]['pib_median'],
                'date': str(pib.iloc[0]['date'].date()),
                'year': pib.iloc[0].get('reference_year', datetime.now().year)
            }
        
        # Câmbio
        cambio = self.get_cambio_expectations(last_n_weeks=2)
        if not cambio.empty:
            summary['cambio'] = {
                'value': cambio.iloc[0]['cambio_median'],
                'date': str(cambio.iloc[0]['date'].date())
            }
        
        return summary


def fetch_focus_data(indicators: List[str] = None, weeks: int = 12) -> pd.DataFrame:
    """
    Função de conveniência para buscar dados Focus.
    
    Args:
        indicators: Lista de indicadores ('ipca', 'selic', 'pib', 'cambio').
                   Se None, busca todos.
        weeks: Número de semanas.
        
    Returns:
        DataFrame consolidado com todas as expectativas.
    """
    client = FocusClient()
    
    if indicators is None:
        indicators = ['ipca', 'selic', 'pib', 'cambio']
    
    all_data = []
    
    for ind in indicators:
        ind = ind.lower()
        
        if ind == 'ipca':
            df = client.get_ipca_expectations(weeks)
            if not df.empty:
                df['indicator'] = 'IPCA'
                df['value'] = df['ipca_median']
                all_data.append(df[['date', 'indicator', 'value']])
                
        elif ind == 'selic':
            df = client.get_selic_expectations(weeks)
            if not df.empty:
                df['indicator'] = 'SELIC'
                df['value'] = df['selic_median']
                all_data.append(df[['date', 'indicator', 'value']])
                
        elif ind == 'pib':
            df = client.get_pib_expectations(last_n_weeks=weeks)
            if not df.empty:
                df['indicator'] = 'PIB'
                df['value'] = df['pib_median']
                all_data.append(df[['date', 'indicator', 'value']])
                
        elif ind == 'cambio':
            df = client.get_cambio_expectations(last_n_weeks=weeks)
            if not df.empty:
                df['indicator'] = 'CAMBIO'
                df['value'] = df['cambio_median']
                all_data.append(df[['date', 'indicator', 'value']])
    
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return pd.DataFrame()


if __name__ == "__main__":
    # Test the client
    logging.basicConfig(level=logging.INFO)
    
    client = FocusClient()
    
    print("\n=== IPCA Expectations ===")
    ipca = client.get_ipca_expectations(last_n_weeks=4)
    print(ipca.head())
    
    print("\n=== SELIC Expectations ===")
    selic = client.get_selic_expectations(last_n_weeks=4)
    print(selic.head())
    
    print("\n=== Latest Summary ===")
    summary = client.get_latest_summary()
    for key, value in summary.items():
        print(f"{key}: {value}")
