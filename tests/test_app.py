"""Tests for tx_lsp/api/app.py — FastAPI app factory."""

import pytest
from fastapi.testclient import TestClient


# ── create_app ────────────────────────────────────────────────


class TestCreateApp:
    def test_creates_app(self):
        from tx_lsp.api.app import create_app

        app = create_app()
        assert app is not None

    def test_app_has_routes(self):
        from tx_lsp.api.app import create_app

        app = create_app()
        paths = [route.path for route in app.routes]
        assert "/health" in paths
        assert "/info" in paths
        assert "/capabilities" in paths

    def test_health_endpoint(self):
        from tx_lsp.api.app import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}

    def test_with_api_key(self):
        from tx_lsp.api.app import create_app

        app = create_app(api_key="test-secret")
        client = TestClient(app)

        # Public endpoints should work without key
        resp = client.get("/health")
        assert resp.status_code == 200

        # Protected endpoint without key should fail
        resp = client.post("/validate", json={"source": "test"})
        assert resp.status_code in (401, 403, 422)

    def test_with_api_key_authorized(self):
        from tx_lsp.api.app import create_app

        app = create_app(api_key="test-secret")
        client = TestClient(app)

        # Protected endpoint with correct key
        resp = client.post(
            "/validate",
            json={"source": "test"},
            headers={"X-API-Key": "test-secret"},
        )
        # Should not be 401/403 (may be 503 if no language discovered)
        assert resp.status_code != 401

    def test_with_api_key_wrong_key(self):
        from tx_lsp.api.app import create_app

        app = create_app(api_key="test-secret")
        client = TestClient(app)

        resp = client.post(
            "/validate",
            json={"source": "test"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 401

    def test_with_extra_patterns(self):
        from tx_lsp.api.app import create_app

        # Should not crash with extra patterns even if language doesn't exist
        app = create_app(extra_patterns={"*.custom": "nonexistent"})
        assert app is not None

    def test_app_metadata(self):
        from tx_lsp.api.app import create_app

        app = create_app()
        assert app.title == "tx-lsp API"
        assert "Rosetta" in app.description
