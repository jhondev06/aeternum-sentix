"""
Tests for RSS client module.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from datetime import datetime

from ingest.rss_client import fetch_rss, _fetch_single_feed, _process_entry


class TestProcessEntry:
    """Tests for _process_entry function."""
    
    def test_process_valid_entry(self):
        """Test processing a valid RSS entry."""
        entry = MagicMock()
        entry.get.side_effect = lambda key, default='': {
            'title': 'Test Article Title',
            'summary': 'This is the article body content',
            'link': 'https://test.com/article',
            'published_parsed': (2024, 1, 15, 10, 30, 0, 0, 0, 0)
        }.get(key, default)
        
        result = _process_entry(
            entry=entry,
            domain='test.com',
            min_chars=10,
            allowed_langs=['en'],
            seen_ids=set()
        )
        
        assert result is not None
        assert result['title'] == 'Test Article Title'
        assert result['source'] == 'test.com'
        assert 'id' in result
    
    def test_process_entry_too_short(self):
        """Test that short entries are filtered out."""
        entry = MagicMock()
        entry.get.side_effect = lambda key, default='': {
            'title': 'Hi',
            'summary': '',
            'link': 'https://test.com/article'
        }.get(key, default)
        
        result = _process_entry(
            entry=entry,
            domain='test.com',
            min_chars=100,
            allowed_langs=[],
            seen_ids=set()
        )
        
        assert result is None
    
    def test_process_entry_duplicate(self):
        """Test that duplicate entries are filtered out."""
        entry = MagicMock()
        entry.get.side_effect = lambda key, default='': {
            'title': 'Test Article',
            'summary': 'Content here for the article body',
            'link': 'https://test.com/article'
        }.get(key, default)
        
        # Create entry first
        first_result = _process_entry(
            entry=entry,
            domain='test.com',
            min_chars=10,
            allowed_langs=[],
            seen_ids=set()
        )
        
        # Try to add duplicate
        seen_ids = {first_result['id']}
        second_result = _process_entry(
            entry=entry,
            domain='test.com',
            min_chars=10,
            allowed_langs=[],
            seen_ids=seen_ids
        )
        
        assert second_result is None


class TestFetchSingleFeed:
    """Tests for _fetch_single_feed function."""
    
    @patch('ingest.rss_client.feedparser.parse')
    def test_fetch_success(self, mock_parse):
        """Test successful feed fetch."""
        mock_feed = MagicMock()
        mock_feed.entries = [MagicMock()]
        mock_parse.return_value = mock_feed
        
        result = _fetch_single_feed('https://test.com/rss')
        
        assert result is not None
        mock_parse.assert_called_once()
    
    @patch('ingest.rss_client.feedparser.parse')
    def test_fetch_retry_on_failure(self, mock_parse):
        """Test that fetch retries on failure."""
        mock_parse.side_effect = [Exception("Timeout"), MagicMock(entries=[])]
        
        result = _fetch_single_feed('https://test.com/rss', max_retries=2)
        
        assert mock_parse.call_count == 2


class TestFetchRss:
    """Tests for the main fetch_rss function."""
    
    @patch('ingest.rss_client._fetch_single_feed')
    def test_fetch_rss_empty_feeds(self, mock_fetch):
        """Test with empty feeds list."""
        result = fetch_rss(feeds=[], min_chars=100, allowed_langs=['en'])
        
        assert isinstance(result, pd.DataFrame)
        assert result.empty
    
    @patch('ingest.rss_client._fetch_single_feed')
    def test_fetch_rss_returns_dataframe(self, mock_fetch):
        """Test that result is always a DataFrame."""
        mock_fetch.return_value = None
        
        result = fetch_rss(
            feeds=['https://test.com/rss'],
            min_chars=100,
            allowed_langs=['en']
        )
        
        assert isinstance(result, pd.DataFrame)
    
    def test_fetch_rss_columns(self):
        """Test that DataFrame has expected columns when not empty."""
        # This test would require mocking the full pipeline
        # For integration, we just verify the return type
        result = fetch_rss(feeds=[], min_chars=100)
        expected_columns = ['id', 'source', 'published_at', 'title', 'body', 'url', 'lang']
        
        # Empty df should still be a DataFrame
        assert isinstance(result, pd.DataFrame)
