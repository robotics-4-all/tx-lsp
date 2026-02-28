"""Tests for tx_lsp/server.py — TxLanguageServer and create_server."""

from tx_lsp.server import TxLanguageServer, create_server
from tx_lsp.discovery import LanguageRegistry
from tx_lsp.workspace import ModelManager


class TestTxLanguageServer:
    def test_has_registry(self):
        server = TxLanguageServer()
        assert isinstance(server.registry, LanguageRegistry)

    def test_has_model_manager(self):
        server = TxLanguageServer()
        assert isinstance(server.model_manager, ModelManager)

    def test_server_name(self):
        server = TxLanguageServer()
        assert server.name == "tx-lsp"


class TestCreateServer:
    def test_returns_server(self):
        server = create_server()
        assert isinstance(server, TxLanguageServer)

    def test_with_extra_patterns(self):
        server = create_server(extra_patterns={"*.custom": "testlang"})
        assert isinstance(server, TxLanguageServer)

    def test_without_extra_patterns(self):
        server = create_server()
        assert isinstance(server, TxLanguageServer)

    def test_without_extra_patterns_none(self):
        server = create_server(extra_patterns=None)
        assert isinstance(server, TxLanguageServer)
