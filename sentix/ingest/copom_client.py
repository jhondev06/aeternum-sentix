"""
COPOM Client - Integração com comunicados e atas do COPOM.

Este módulo faz scraping dos comunicados e atas do COPOM
disponíveis no site do Banco Central.

Fonte: https://www.bcb.gov.br/publicacoes/atascopom
"""

from typing import Dict, List, Any, Optional
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)

# URLs do BCB
BCB_BASE = "https://www.bcb.gov.br"
ATAS_URL = f"{BCB_BASE}/publicacoes/atascopom"
COMUNICADOS_URL = f"{BCB_BASE}/publicacoes/copom"


class CopomClient:
    """
    Cliente para acessar documentos do COPOM.
    
    Permite obter lista de atas, comunicados e analisar
    o tom (hawkish/dovish) dos textos.
    
    Example:
        >>> client = CopomClient()
        >>> atas = client.list_atas(last_n=5)
        >>> print(atas)
    """
    
    def __init__(self, timeout: int = 30):
        """
        Inicializa o cliente COPOM.
        
        Args:
            timeout: Timeout para requests em segundos.
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Palavras-chave para análise de tom
        self.hawkish_words = [
            'inflação', 'pressão', 'alta', 'elevação', 'preocupação',
            'vigilância', 'ajuste', 'aperto', 'risco', 'incerteza',
            'cauteloso', 'persistente', 'desancorar', 'expectativas'
        ]
        
        self.dovish_words = [
            'queda', 'redução', 'arrefecimento', 'moderação', 'convergência',
            'benigno', 'favorável', 'flexibilização', 'acomodatício',
            'ancoradas', 'estabilidade', 'melhora'
        ]
    
    def list_atas(self, last_n: int = 10) -> pd.DataFrame:
        """
        Lista as últimas atas do COPOM disponíveis.
        
        Args:
            last_n: Número de atas para listar.
            
        Returns:
            DataFrame com colunas: number, date, title, url
        """
        try:
            response = self.session.get(ATAS_URL, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            atas = []
            
            # Procura links de atas
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # Atas geralmente têm padrão "Ata nº XXX"
                if 'ata' in text.lower() and ('copom' in href.lower() or 'ata' in href.lower()):
                    # Extrai número da ata
                    match = re.search(r'(\d+)', text)
                    number = int(match.group(1)) if match else 0
                    
                    # Monta URL completa
                    url = href if href.startswith('http') else BCB_BASE + href
                    
                    atas.append({
                        'number': number,
                        'title': text,
                        'url': url
                    })
            
            # Remove duplicatas e ordena
            df = pd.DataFrame(atas).drop_duplicates(subset=['number'])
            df = df.sort_values('number', ascending=False).head(last_n)
            
            logger.info(f"Found {len(df)} COPOM atas")
            return df.reset_index(drop=True)
            
        except requests.RequestException as e:
            logger.error(f"Error fetching COPOM atas list: {e}")
            return pd.DataFrame()
    
    def get_comunicado_text(self, url: str) -> Optional[str]:
        """
        Obtém o texto de um comunicado/ata.
        
        Args:
            url: URL do comunicado.
            
        Returns:
            Texto do comunicado ou None se erro.
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Tenta encontrar o conteúdo principal
            content_div = soup.find('div', class_='content') or soup.find('article')
            
            if content_div:
                # Remove scripts e estilos
                for tag in content_div.find_all(['script', 'style']):
                    tag.decompose()
                
                text = content_div.get_text(separator=' ', strip=True)
                return text
            
            # Fallback: pega todo o body
            body = soup.find('body')
            if body:
                return body.get_text(separator=' ', strip=True)
            
            return None
            
        except requests.RequestException as e:
            logger.error(f"Error fetching comunicado: {e}")
            return None
    
    def analyze_tone(self, text: str) -> Dict[str, Any]:
        """
        Analisa o tom de um texto do COPOM.
        
        Usa contagem de palavras-chave para determinar
        se o tom é hawkish (contracionista) ou dovish (expansionista).
        
        Args:
            text: Texto para analisar.
            
        Returns:
            Dicionário com análise de tom.
        """
        text_lower = text.lower()
        
        # Conta palavras hawkish e dovish
        hawkish_count = sum(1 for word in self.hawkish_words if word in text_lower)
        dovish_count = sum(1 for word in self.dovish_words if word in text_lower)
        
        total = hawkish_count + dovish_count
        
        if total == 0:
            tone_score = 0
            tone_label = 'neutro'
        else:
            # Score de -1 (muito dovish) a +1 (muito hawkish)
            tone_score = (hawkish_count - dovish_count) / total
            
            if tone_score > 0.3:
                tone_label = 'hawkish'
            elif tone_score < -0.3:
                tone_label = 'dovish'
            else:
                tone_label = 'neutro'
        
        return {
            'tone_score': round(tone_score, 3),
            'tone_label': tone_label,
            'hawkish_count': hawkish_count,
            'dovish_count': dovish_count,
            'total_keywords': total,
            'text_length': len(text)
        }
    
    def get_latest_tone_analysis(self) -> Dict[str, Any]:
        """
        Obtém análise de tom da ata mais recente.
        
        Returns:
            Dicionário com análise completa.
        """
        atas = self.list_atas(last_n=1)
        
        if atas.empty:
            return {'error': 'No atas found'}
        
        latest_ata = atas.iloc[0]
        text = self.get_comunicado_text(latest_ata['url'])
        
        if text is None:
            return {'error': 'Could not fetch ata text'}
        
        analysis = self.analyze_tone(text)
        analysis['ata_number'] = latest_ata['number']
        analysis['title'] = latest_ata['title']
        analysis['url'] = latest_ata['url']
        
        return analysis
    
    def get_historical_tones(self, last_n: int = 8) -> pd.DataFrame:
        """
        Obtém análise de tom de múltiplas atas.
        
        Args:
            last_n: Número de atas para analisar.
            
        Returns:
            DataFrame com análise de tom por ata.
        """
        atas = self.list_atas(last_n=last_n)
        
        if atas.empty:
            return pd.DataFrame()
        
        results = []
        
        for _, ata in atas.iterrows():
            text = self.get_comunicado_text(ata['url'])
            
            if text:
                analysis = self.analyze_tone(text)
                analysis['number'] = ata['number']
                analysis['title'] = ata['title']
                results.append(analysis)
        
        return pd.DataFrame(results)


def fetch_copom_tone(last_n: int = 1) -> Dict[str, Any]:
    """
    Função de conveniência para obter tom do COPOM.
    
    Args:
        last_n: Número de atas para analisar.
        
    Returns:
        Dicionário com análise ou lista de análises.
    """
    client = CopomClient()
    
    if last_n == 1:
        return client.get_latest_tone_analysis()
    else:
        return client.get_historical_tones(last_n).to_dict('records')


if __name__ == "__main__":
    # Test the client
    logging.basicConfig(level=logging.INFO)
    
    client = CopomClient()
    
    print("\n=== Latest COPOM Atas ===")
    atas = client.list_atas(last_n=5)
    print(atas)
    
    print("\n=== Latest Tone Analysis ===")
    tone = client.get_latest_tone_analysis()
    print(tone)
