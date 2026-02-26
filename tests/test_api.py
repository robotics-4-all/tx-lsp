"""Tests for the REST API — rosetta Backend API Contract."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from textx import metamodel_from_str

from tx_lsp.api.routes import init_routes, public_router, router
from tx_lsp.discovery import LanguageInfo, LanguageRegistry
from tx_lsp.workspace import ModelManager

GRAMMAR = """
Model: items+=Item;
Item: 'item' name=ID '{' value=INT '}';
"""

VALID_SOURCE = "item foo { 42 }"
INVALID_SOURCE = "this is not valid at all"


@pytest.fixture()
def client():
    registry = LanguageRegistry()
    lang = LanguageInfo(
        name="testlang",
        pattern="*.test",
        description="Test language",
        metamodel_factory=lambda: metamodel_from_str(GRAMMAR),
    )
    registry._languages["testlang"] = lang

    model_manager = ModelManager(registry)

    app = FastAPI()
    init_routes(registry, model_manager)
    app.include_router(public_router)
    app.include_router(router)

    return TestClient(app)


# ── GET /health ────────────────────────────────────────────────


class TestHealth:
    def test_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_status_healthy(self, client):
        assert client.get("/health").json() == {"status": "healthy"}


# ── GET /info ──────────────────────────────────────────────────


class TestInfo:
    def test_returns_200(self, client):
        assert client.get("/info").status_code == 200

    def test_contains_language_metadata(self, client):
        data = client.get("/info").json()
        assert data["name"] == "testlang"
        assert data["language_id"] == "testlang"
        assert ".test" in data["file_extensions"]

    def test_contains_version(self, client):
        data = client.get("/info").json()
        assert "version" in data
        assert isinstance(data["version"], str)


# ── GET /capabilities ─────────────────────────────────────────


class TestCapabilities:
    def test_returns_200(self, client):
        assert client.get("/capabilities").status_code == 200

    def test_validation_enabled(self, client):
        assert client.get("/capabilities").json()["validation"] is True

    def test_completion_enabled(self, client):
        assert client.get("/capabilities").json()["completion"] is True

    def test_hover_enabled(self, client):
        assert client.get("/capabilities").json()["hover"] is True

    def test_has_all_capability_fields(self, client):
        data = client.get("/capabilities").json()
        for field in (
            "validation",
            "generation",
            "completion",
            "hover",
            "formatting",
            "goto_definition",
            "find_references",
        ):
            assert field in data
        assert "generation_targets" in data


# ── GET /keywords ──────────────────────────────────────────────


class TestKeywords:
    def test_returns_200(self, client):
        assert client.get("/keywords").status_code == 200

    def test_returns_list(self, client):
        data = client.get("/keywords").json()
        assert isinstance(data, list)

    def test_items_have_completion_fields(self, client):
        data = client.get("/keywords").json()
        for item in data:
            assert "label" in item
            assert "kind" in item


# ── POST /validate ─────────────────────────────────────────────


class TestValidate:
    def test_valid_source(self, client):
        resp = client.post("/validate", json={"source": VALID_SOURCE})
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["diagnostics"] == []

    def test_invalid_source(self, client):
        resp = client.post("/validate", json={"source": INVALID_SOURCE})
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert len(data["diagnostics"]) > 0

    def test_diagnostic_shape(self, client):
        resp = client.post("/validate", json={"source": INVALID_SOURCE})
        diag = resp.json()["diagnostics"][0]
        assert "range" in diag
        assert "start" in diag["range"]
        assert "end" in diag["range"]
        assert "line" in diag["range"]["start"]
        assert "character" in diag["range"]["start"]
        assert "message" in diag
        assert isinstance(diag["severity"], int)

    def test_validate_with_uri(self, client):
        resp = client.post(
            "/validate",
            json={
                "source": VALID_SOURCE,
                "uri": "file:///tmp/model.test",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_multiple_items(self, client):
        source = "item a { 1 } item b { 2 } item c { 3 }"
        resp = client.post("/validate", json={"source": source})
        assert resp.json()["valid"] is True


# ── POST /validate/file ────────────────────────────────────────


class TestValidateFile:
    def test_valid_file(self, client):
        resp = client.post(
            "/validate/file",
            files={"file": ("model.test", VALID_SOURCE.encode(), "text/plain")},
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_invalid_file(self, client):
        resp = client.post(
            "/validate/file",
            files={"file": ("model.test", INVALID_SOURCE.encode(), "text/plain")},
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is False


# ── POST /complete ─────────────────────────────────────────────


class TestComplete:
    def test_returns_200(self, client):
        resp = client.post(
            "/complete",
            json={
                "source": VALID_SOURCE,
                "position": {"line": 0, "character": 0},
            },
        )
        assert resp.status_code == 200

    def test_returns_items_list(self, client):
        resp = client.post(
            "/complete",
            json={
                "source": VALID_SOURCE,
                "position": {"line": 0, "character": 0},
            },
        )
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_includes_named_objects(self, client):
        resp = client.post(
            "/complete",
            json={
                "source": VALID_SOURCE,
                "position": {"line": 0, "character": 0},
            },
        )
        labels = [item["label"] for item in resp.json()["items"]]
        assert "foo" in labels

    def test_completion_item_shape(self, client):
        resp = client.post(
            "/complete",
            json={
                "source": VALID_SOURCE,
                "position": {"line": 0, "character": 0},
            },
        )
        for item in resp.json()["items"]:
            assert "label" in item
            assert "kind" in item


# ── POST /hover ────────────────────────────────────────────────


class TestHover:
    def test_returns_200(self, client):
        resp = client.post(
            "/hover",
            json={
                "source": VALID_SOURCE,
                "position": {"line": 0, "character": 5},
            },
        )
        assert resp.status_code == 200

    def test_hover_on_invalid_source(self, client):
        resp = client.post(
            "/hover",
            json={
                "source": INVALID_SOURCE,
                "position": {"line": 0, "character": 0},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["content"] is None

    def test_hover_at_out_of_range_position(self, client):
        resp = client.post(
            "/hover",
            json={
                "source": VALID_SOURCE,
                "position": {"line": 99, "character": 0},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["content"] is None


# ── POST /generate ─────────────────────────────────────────────


class TestGenerate:
    def test_missing_target_returns_400(self, client):
        resp = client.post("/generate", json={"source": VALID_SOURCE})
        assert resp.status_code == 400

    def test_invalid_source_returns_diagnostics(self, client):
        resp = client.post(
            "/generate",
            json={
                "source": INVALID_SOURCE,
                "target": "python",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["artifacts"] == {}
        assert len(data["diagnostics"]) > 0

    def test_unknown_generator_returns_404(self, client):
        resp = client.post(
            "/generate",
            json={
                "source": VALID_SOURCE,
                "target": "nonexistent_target",
            },
        )
        assert resp.status_code == 404
