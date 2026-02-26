"""Tests for tx_lsp/workspace.py — model parsing and caching."""

import pytest
from lsprotocol import types
from textx import metamodel_from_str

from tx_lsp.discovery import LanguageInfo, LanguageRegistry
from tx_lsp.workspace import ModelManager, ModelState

GRAMMAR = """
Model: items+=Item;
Item: 'item' name=ID '{' value=INT '}';
"""

VALID_SOURCE = "item foo { 42 }"
INVALID_SOURCE = "this is not valid at all"


def _make_registry():
    registry = LanguageRegistry()
    lang = LanguageInfo(
        name="testlang",
        pattern="*.test",
        description="Test language",
        metamodel_factory=lambda: metamodel_from_str(GRAMMAR),
    )
    registry._languages["testlang"] = lang
    return registry


# ── ModelState ────────────────────────────────────────────────


class TestModelState:
    def test_initial_state(self):
        state = ModelState("file:///test.test")
        assert state.uri == "file:///test.test"
        assert state.model is None
        assert state.diagnostics == []
        assert state.source == ""
        assert state.version is None

    def test_is_valid_no_model(self):
        state = ModelState("file:///test.test")
        assert state.is_valid is False

    def test_is_valid_with_model_no_diagnostics(self):
        state = ModelState("file:///test.test")
        state.model = object()  # any truthy value
        assert state.is_valid is True

    def test_is_valid_with_model_and_diagnostics(self):
        state = ModelState("file:///test.test")
        state.model = object()
        state.diagnostics = [
            types.Diagnostic(
                range=types.Range(
                    start=types.Position(line=0, character=0),
                    end=types.Position(line=0, character=1),
                ),
                message="error",
                severity=types.DiagnosticSeverity.Error,
            )
        ]
        assert state.is_valid is False

    def test_version_stored(self):
        state = ModelState("file:///test.test", version=3)
        assert state.version == 3


# ── ModelManager ──────────────────────────────────────────────


class TestModelManager:
    @pytest.fixture()
    def manager(self):
        return ModelManager(_make_registry())

    def test_get_state_empty(self, manager):
        assert manager.get_state("file:///unknown.test") is None

    def test_parse_valid_document(self, manager, tmp_path):
        uri = f"file://{tmp_path}/model.test"
        state = manager.parse_document(uri, VALID_SOURCE)
        assert state is not None
        assert state.is_valid
        assert state.model is not None
        assert state.diagnostics == []
        assert state.source == VALID_SOURCE

    def test_parse_invalid_document(self, manager, tmp_path):
        uri = f"file://{tmp_path}/model.test"
        state = manager.parse_document(uri, INVALID_SOURCE)
        assert state is not None
        assert state.is_valid is False
        assert state.model is None
        assert len(state.diagnostics) > 0

    def test_diagnostic_shape(self, manager, tmp_path):
        uri = f"file://{tmp_path}/model.test"
        state = manager.parse_document(uri, INVALID_SOURCE)
        diag = state.diagnostics[0]
        assert isinstance(diag, types.Diagnostic)
        assert diag.severity == types.DiagnosticSeverity.Error
        assert diag.source == "tx-lsp"
        assert isinstance(diag.message, str)
        assert diag.range.start.line >= 0
        assert diag.range.start.character >= 0

    def test_cached_state(self, manager, tmp_path):
        uri = f"file://{tmp_path}/model.test"
        manager.parse_document(uri, VALID_SOURCE)
        state = manager.get_state(uri)
        assert state is not None
        assert state.is_valid

    def test_reparse_updates_cache(self, manager, tmp_path):
        uri = f"file://{tmp_path}/model.test"
        manager.parse_document(uri, VALID_SOURCE)
        assert manager.get_state(uri).is_valid

        manager.parse_document(uri, INVALID_SOURCE)
        assert manager.get_state(uri).is_valid is False

    def test_remove_document(self, manager, tmp_path):
        uri = f"file://{tmp_path}/model.test"
        manager.parse_document(uri, VALID_SOURCE)
        assert manager.get_state(uri) is not None

        manager.remove_document(uri)
        assert manager.get_state(uri) is None

    def test_remove_nonexistent_document(self, manager):
        # Should not raise
        manager.remove_document("file:///nonexistent.test")

    def test_no_language_for_file(self, manager, tmp_path):
        uri = f"file://{tmp_path}/model.unknown"
        state = manager.parse_document(uri, VALID_SOURCE)
        assert state is None

    def test_version_stored(self, manager, tmp_path):
        uri = f"file://{tmp_path}/model.test"
        state = manager.parse_document(uri, VALID_SOURCE, version=5)
        assert state.version == 5

    def test_multiple_documents(self, manager, tmp_path):
        uri1 = f"file://{tmp_path}/model1.test"
        uri2 = f"file://{tmp_path}/model2.test"
        manager.parse_document(uri1, VALID_SOURCE)
        manager.parse_document(uri2, "item bar { 99 }")

        state1 = manager.get_state(uri1)
        state2 = manager.get_state(uri2)
        assert state1.is_valid
        assert state2.is_valid
        assert state1.model.items[0].name == "foo"
        assert state2.model.items[0].name == "bar"

    def test_textx_error_to_diagnostics(self, manager):
        """Test the internal diagnostic converter."""
        from textx.exceptions import TextXSyntaxError

        err = TextXSyntaxError("Expected 'item'", line=2, col=5, filename="test.test")
        diags = manager._textx_error_to_diagnostics(err)
        assert len(diags) == 1
        assert diags[0].range.start.line == 1
        assert diags[0].range.start.character == 4
        assert "Expected" in diags[0].message
