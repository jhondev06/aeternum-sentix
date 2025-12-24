"""
Tests for the normalize module.
"""

import pytest
import pandas as pd
from ingest.normalize import load_ticker_map, map_entities, _compile_ticker_patterns, _find_tickers_in_text


class TestLoadTickerMap:
    """Tests for load_ticker_map function."""
    
    def test_load_valid_yaml(self, temp_dir):
        """Test loading a valid ticker map YAML file."""
        import os
        yaml_content = """
PETR4.SA:
  aliases: ["Petrobras", "PETR4"]
VALE3.SA:
  aliases: ["Vale", "VALE3"]
"""
        yaml_path = os.path.join(temp_dir, "tickers.yml")
        with open(yaml_path, 'w') as f:
            f.write(yaml_content)
        
        result = load_ticker_map(yaml_path)
        
        assert 'PETR4.SA' in result
        assert 'VALE3.SA' in result
        assert result['PETR4.SA']['aliases'] == ['Petrobras', 'PETR4']
    
    def test_load_nonexistent_file(self):
        """Test that loading a nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_ticker_map('nonexistent_file.yml')


class TestCompileTickerPatterns:
    """Tests for _compile_ticker_patterns function."""
    
    def test_compile_patterns(self, sample_ticker_map):
        """Test that patterns are compiled correctly."""
        regex_map = _compile_ticker_patterns(sample_ticker_map)
        
        assert 'PETR4.SA' in regex_map
        assert 'VALE3.SA' in regex_map
        assert regex_map['PETR4.SA'].search('Petrobras stock')
        assert regex_map['VALE3.SA'].search('Vale mining')
    
    def test_case_insensitive(self, sample_ticker_map):
        """Test that pattern matching is case-insensitive."""
        regex_map = _compile_ticker_patterns(sample_ticker_map)
        
        assert regex_map['PETR4.SA'].search('PETROBRAS')
        assert regex_map['PETR4.SA'].search('petrobras')


class TestFindTickersInText:
    """Tests for _find_tickers_in_text function."""
    
    def test_find_single_ticker(self, sample_ticker_map):
        """Test finding a single ticker in text."""
        regex_map = _compile_ticker_patterns(sample_ticker_map)
        
        result = _find_tickers_in_text("Petrobras reports earnings", regex_map)
        
        assert 'PETR4.SA' in result
        assert len(result) == 1
    
    def test_find_multiple_tickers(self, sample_ticker_map):
        """Test finding multiple tickers in text."""
        regex_map = _compile_ticker_patterns(sample_ticker_map)
        
        result = _find_tickers_in_text("Petrobras and Vale both up", regex_map)
        
        assert 'PETR4.SA' in result
        assert 'VALE3.SA' in result
    
    def test_find_no_tickers(self, sample_ticker_map):
        """Test text with no matching tickers."""
        regex_map = _compile_ticker_patterns(sample_ticker_map)
        
        result = _find_tickers_in_text("Random text about nothing", regex_map)
        
        assert len(result) == 0


class TestMapEntities:
    """Tests for map_entities function."""
    
    def test_map_entities_basic(self, sample_articles_df, sample_ticker_map):
        """Test basic entity mapping."""
        result = map_entities(sample_articles_df, sample_ticker_map)
        
        assert not result.empty
        assert 'ticker' in result.columns
        assert 'PETR4.SA' in result['ticker'].values
    
    def test_map_entities_explodes_correctly(self, sample_ticker_map):
        """Test that articles with multiple tickers are exploded."""
        df = pd.DataFrame({
            'id': ['test1'],
            'title': ['Petrobras and Vale announce merger'],
            'body': ['The oil and mining companies are combining'],
            'source': ['test.com'],
            'published_at': ['2024-01-01T10:00:00Z'],
            'url': ['https://test.com'],
            'lang': ['en']
        })
        
        result = map_entities(df, sample_ticker_map)
        
        # Should have 2 rows (one per ticker)
        assert len(result) == 2
        assert set(result['ticker'].values) == {'PETR4.SA', 'VALE3.SA'}
    
    def test_map_entities_empty_df(self, sample_ticker_map):
        """Test handling of empty DataFrame."""
        df = pd.DataFrame(columns=['id', 'title', 'body', 'source', 'published_at', 'url', 'lang'])
        
        result = map_entities(df, sample_ticker_map)
        
        assert result.empty
    
    def test_map_entities_no_matches(self, sample_ticker_map):
        """Test when no articles match any tickers."""
        df = pd.DataFrame({
            'id': ['test1'],
            'title': ['Random news about weather'],
            'body': ['It is raining today'],
            'source': ['test.com'],
            'published_at': ['2024-01-01T10:00:00Z'],
            'url': ['https://test.com'],
            'lang': ['en']
        })
        
        result = map_entities(df, sample_ticker_map)
        
        assert result.empty
    
    def test_map_entities_none_values(self, sample_ticker_map):
        """Test handling of None values in title/body."""
        df = pd.DataFrame({
            'id': ['test1'],
            'title': [None],
            'body': ['Petrobras reports earnings'],
            'source': ['test.com'],
            'published_at': ['2024-01-01T10:00:00Z'],
            'url': ['https://test.com'],
            'lang': ['en']
        })
        
        result = map_entities(df, sample_ticker_map)
        
        assert not result.empty
        assert 'PETR4.SA' in result['ticker'].values
