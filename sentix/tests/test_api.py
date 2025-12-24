"""
Tests for the FastAPI application.
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path
import base64

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def client():
    """Create test client for the API."""
    from api.app import app
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create authentication headers."""
    # Default credentials from config
    credentials = base64.b64encode(b"admin:sentix123").decode("utf-8")
    return {"Authorization": f"Basic {credentials}"}


class TestHealthEndpoint:
    """Tests for the health check endpoint."""
    
    def test_health_check(self, client):
        """Test that health endpoint returns 200."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestAuthentication:
    """Tests for API authentication."""
    
    def test_unauthenticated_request(self, client):
        """Test that unauthenticated requests are rejected."""
        response = client.get("/signal", params={"ticker": "PETR4.SA"})
        
        assert response.status_code == 401
    
    def test_wrong_credentials(self, client):
        """Test that wrong credentials are rejected."""
        credentials = base64.b64encode(b"wrong:wrong").decode("utf-8")
        headers = {"Authorization": f"Basic {credentials}"}
        
        response = client.get("/signal", params={"ticker": "PETR4.SA"}, headers=headers)
        
        assert response.status_code == 401
    
    def test_valid_credentials(self, client, auth_headers):
        """Test that valid credentials are accepted."""
        response = client.get("/signal", params={"ticker": "PETR4.SA"}, headers=auth_headers)
        
        # Should not be 401 (might be 404 if no data, but auth passed)
        assert response.status_code != 401


class TestScoreTextEndpoint:
    """Tests for the /score_text endpoint."""
    
    def test_score_text_basic(self, client, auth_headers):
        """Test basic text scoring."""
        response = client.post(
            "/score_text",
            json={"text": "Stock prices are rising", "ticker": "PETR4.SA"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "score" in data or "prob_up" in data
    
    def test_score_text_empty_text(self, client, auth_headers):
        """Test scoring with empty text."""
        response = client.post(
            "/score_text",
            json={"text": "", "ticker": "PETR4.SA"},
            headers=auth_headers
        )
        
        # Should still return a result (neutral)
        assert response.status_code == 200


class TestSignalEndpoint:
    """Tests for the /signal endpoint."""
    
    def test_signal_missing_ticker(self, client, auth_headers):
        """Test signal endpoint without ticker."""
        response = client.get("/signal", headers=auth_headers)
        
        # Should fail validation or return error
        assert response.status_code in [400, 422]


class TestAlertEndpoints:
    """Tests for alert management endpoints."""
    
    def test_list_alert_rules(self, client, auth_headers):
        """Test listing alert rules."""
        response = client.get("/alerts/rules", headers=auth_headers)
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_list_webhooks(self, client, auth_headers):
        """Test listing webhooks."""
        response = client.get("/alerts/webhooks", headers=auth_headers)
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_get_alert_stats(self, client, auth_headers):
        """Test getting alert statistics."""
        response = client.get("/alerts/stats", headers=auth_headers)
        
        assert response.status_code == 200
