"""tx-lsp Language Server — generic LSP for all textX-based DSLs.

Uses pygls to implement the Language Server Protocol.
Auto-discovers installed textX languages and provides:
- Diagnostics (parse + semantic errors)
- Document symbols (outline)
- Go-to-definition (cross-reference resolution)
- Find references
- Hover information
- Completion (keywords + named references)
"""

import logging

from pygls.lsp.server import LanguageServer
from lsprotocol import types

from tx_lsp import __version__
from tx_lsp.discovery import LanguageRegistry
from tx_lsp.workspace import ModelManager
from tx_lsp.features.diagnostics import publish_diagnostics
from tx_lsp.features.symbols import get_document_symbols
from tx_lsp.features.definition import goto_definition
from tx_lsp.features.hover import get_hover_info
from tx_lsp.features.references import find_references
from tx_lsp.features.completion import get_completions
from tx_lsp.features.semantic_tokens import get_semantic_tokens, TOKEN_TYPES, TOKEN_MODIFIERS

log = logging.getLogger(__name__)


class TxLanguageServer(LanguageServer):
    """Language server for textX-based DSLs."""

    def __init__(self):
        super().__init__("tx-lsp", __version__)
        self.registry = LanguageRegistry()
        self.model_manager = ModelManager(self.registry)


def create_server(extra_patterns=None):
    """Create and configure the language server with all features.

    Args:
        extra_patterns: Optional dict mapping glob patterns to language names.
                       E.g., {'*.auto': 'smauto'} to handle .auto files
                       with the smauto language.
    """
    server = TxLanguageServer()

    # ── Lifecycle ──────────────────────────────────────────────────

    @server.feature(types.INITIALIZE)
    def on_initialize(params: types.InitializeParams):
        log.info("tx-lsp initializing...")
        server.registry.discover()

        # Register any extra file patterns
        if extra_patterns:
            for pattern, lang_name in extra_patterns.items():
                server.registry.register_extra_pattern(pattern, lang_name)

        langs = server.registry.all_languages()
        log.info(
            "Discovered %d language(s): %s",
            len(langs),
            ", ".join(f"{lang.name} ({lang.pattern})" for lang in langs),
        )

        return types.InitializeResult(
            capabilities=types.ServerCapabilities(
                text_document_sync=types.TextDocumentSyncOptions(
                    open_close=True,
                    change=types.TextDocumentSyncKind.Full,
                    save=types.SaveOptions(include_text=True),
                ),
                completion_provider=types.CompletionOptions(
                    trigger_characters=[".", ":", " "],
                ),
                hover_provider=True,
                definition_provider=True,
                references_provider=True,
                document_symbol_provider=True,
            )
        )

    # ── Document Lifecycle ─────────────────────────────────────────

    @server.feature(types.TEXT_DOCUMENT_DID_OPEN)
    def did_open(params: types.DidOpenTextDocumentParams):
        publish_diagnostics(
            server,
            params.text_document.uri,
            params.text_document.text,
            params.text_document.version,
        )

    @server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
    def did_change(params: types.DidChangeTextDocumentParams):
        # Full sync — the last content change has the full text
        if params.content_changes:
            text = params.content_changes[-1].text
            publish_diagnostics(
                server,
                params.text_document.uri,
                text,
                params.text_document.version,
            )

    @server.feature(types.TEXT_DOCUMENT_DID_SAVE)
    def did_save(params: types.DidSaveTextDocumentParams):
        if params.text:
            publish_diagnostics(
                server,
                params.text_document.uri,
                params.text,
            )

    @server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
    def did_close(params: types.DidCloseTextDocumentParams):
        server.model_manager.remove_document(params.text_document.uri)
        server.text_document_publish_diagnostics(
            types.PublishDiagnosticsParams(uri=params.text_document.uri, diagnostics=[])
        )

    # ── Completion ─────────────────────────────────────────────────

    @server.feature(types.TEXT_DOCUMENT_COMPLETION)
    def completion(params: types.CompletionParams):
        return get_completions(server, params.text_document.uri, params.position)

    # ── Hover ──────────────────────────────────────────────────────

    @server.feature(types.TEXT_DOCUMENT_HOVER)
    def hover(params: types.HoverParams):
        return get_hover_info(server, params.text_document.uri, params.position)

    # ── Go-to-Definition ──────────────────────────────────────────

    @server.feature(types.TEXT_DOCUMENT_DEFINITION)
    def definition(params: types.DefinitionParams):
        return goto_definition(server, params.text_document.uri, params.position)

    # ── Find References ───────────────────────────────────────────

    @server.feature(types.TEXT_DOCUMENT_REFERENCES)
    def references(params: types.ReferenceParams):
        return find_references(
            server,
            params.text_document.uri,
            params.position,
            include_declaration=params.context.include_declaration,
        )

    # ── Document Symbols ──────────────────────────────────────────

    @server.feature(types.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    def document_symbol(params: types.DocumentSymbolParams):
        return get_document_symbols(server, params.text_document.uri)

    # ── Semantic Tokens ───────────────────────────────────────────

    @server.feature(
        types.TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL,
        types.SemanticTokensLegend(
            token_types=TOKEN_TYPES,
            token_modifiers=TOKEN_MODIFIERS,
        ),
    )
    def semantic_tokens_full(params: types.SemanticTokensParams):
        return get_semantic_tokens(server, params.text_document.uri)

    return server
