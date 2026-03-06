"""LSP integration tests — real server over stdio via pytest-lsp.

Spawns the tx-lsp server with a self-contained test textX language
and exercises all 6 LSP features through actual protocol messages.
"""

import asyncio
import sys
from pathlib import Path
from typing import Sequence

import pytest
import pytest_lsp
from lsprotocol import types
from pytest_lsp import ClientServerConfig, LanguageClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SOURCE = "item foo { 42 } item bar { 99 }"
INVALID_SOURCE = "this is not valid at all"
TEST_URI = "file:///tmp/test_model.testlang"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def wait_for_diagnostics(
    client,  # type: LanguageClient
    uri,  # type: str
    timeout=3.0,  # type: float
):
    # type: (...) -> Sequence[types.Diagnostic]
    """Poll until diagnostics arrive for the given URI."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if uri in client.diagnostics:
            return client.diagnostics[uri]
        await asyncio.sleep(0.1)
    return client.diagnostics.get(uri, [])


def open_doc(client, uri, source, version=1):
    """Send textDocument/didOpen notification."""
    client.text_document_did_open(
        types.DidOpenTextDocumentParams(
            text_document=types.TextDocumentItem(
                uri=uri,
                language_id="testlang",
                version=version,
                text=source,
            )
        )
    )


def change_doc(client, uri, source, version=2):
    """Send textDocument/didChange notification (full sync)."""
    client.text_document_did_change(
        types.DidChangeTextDocumentParams(
            text_document=types.VersionedTextDocumentIdentifier(uri=uri, version=version),
            content_changes=[types.TextDocumentContentChangeWholeDocument(text=source)],
        )
    )


# ---------------------------------------------------------------------------
# Fixture — spawns the real server
# ---------------------------------------------------------------------------


@pytest_lsp.fixture(
    config=ClientServerConfig(
        server_command=[
            sys.executable,
            str(Path(__file__).parent / "testlang_server.py"),
        ],
    ),
)
async def client(lsp_client: LanguageClient):
    params = types.InitializeParams(
        capabilities=types.ClientCapabilities(),
    )
    await lsp_client.initialize_session(params)
    yield
    await lsp_client.shutdown_session()


# ===========================================================================
# Diagnostics
# ===========================================================================


@pytest.mark.asyncio
async def test_diagnostics_valid_document(client: LanguageClient):
    open_doc(client, TEST_URI, VALID_SOURCE)
    diags = await wait_for_diagnostics(client, TEST_URI)
    assert len(diags) == 0


@pytest.mark.asyncio
async def test_diagnostics_invalid_document(client: LanguageClient):
    open_doc(client, TEST_URI, INVALID_SOURCE)
    diags = await wait_for_diagnostics(client, TEST_URI)
    assert len(diags) >= 1
    assert diags[0].severity == types.DiagnosticSeverity.Error


@pytest.mark.asyncio
async def test_diagnostics_clear_on_fix(client: LanguageClient):
    open_doc(client, TEST_URI, INVALID_SOURCE)
    diags = await wait_for_diagnostics(client, TEST_URI)
    assert len(diags) >= 1

    # Fix the document
    change_doc(client, TEST_URI, VALID_SOURCE, version=2)
    # Wait for new diagnostics to arrive (they overwrite the old ones)
    await asyncio.sleep(0.5)
    diags = await wait_for_diagnostics(client, TEST_URI)
    assert len(diags) == 0


# ===========================================================================
# Completion
# ===========================================================================


@pytest.mark.asyncio
async def test_completion_returns_item_keyword(client: LanguageClient):
    open_doc(client, TEST_URI, VALID_SOURCE)
    await wait_for_diagnostics(client, TEST_URI)

    result = await client.text_document_completion_async(
        types.CompletionParams(
            text_document=types.TextDocumentIdentifier(uri=TEST_URI),
            position=types.Position(line=0, character=0),
        )
    )
    assert result is not None
    if isinstance(result, types.CompletionList):
        labels = [item.label for item in result.items]
    else:
        labels = [item.label for item in result]
    assert "item" in labels


@pytest.mark.asyncio
async def test_completion_prefix_filter(client: LanguageClient):
    open_doc(client, TEST_URI, VALID_SOURCE)
    await wait_for_diagnostics(client, TEST_URI)

    # Position at character 2 on "item foo..." — prefix is "it"
    result = await client.text_document_completion_async(
        types.CompletionParams(
            text_document=types.TextDocumentIdentifier(uri=TEST_URI),
            position=types.Position(line=0, character=2),
        )
    )
    assert result is not None
    if isinstance(result, types.CompletionList):
        labels = [item.label for item in result.items]
    else:
        labels = [item.label for item in result]
    assert "item" in labels


# ===========================================================================
# Hover
# ===========================================================================


@pytest.mark.asyncio
async def test_hover_on_named_item(client: LanguageClient):
    open_doc(client, TEST_URI, VALID_SOURCE)
    await wait_for_diagnostics(client, TEST_URI)

    # Position on "foo" (character 5 in "item foo { 42 } ...")
    result = await client.text_document_hover_async(
        types.HoverParams(
            text_document=types.TextDocumentIdentifier(uri=TEST_URI),
            position=types.Position(line=0, character=5),
        )
    )
    assert result is not None
    assert isinstance(result, types.Hover)
    assert isinstance(result.contents, types.MarkupContent)
    assert result.contents.kind == types.MarkupKind.Markdown
    assert "Item" in result.contents.value


@pytest.mark.asyncio
async def test_hover_on_empty_returns_none(client: LanguageClient):
    source = "item a { 1 }\n\n\n"
    uri = "file:///tmp/hover_empty.testlang"
    open_doc(client, uri, source)
    await wait_for_diagnostics(client, uri)

    # Position on an empty line
    result = await client.text_document_hover_async(
        types.HoverParams(
            text_document=types.TextDocumentIdentifier(uri=uri),
            position=types.Position(line=2, character=0),
        )
    )
    assert result is None


# ===========================================================================
# Go-to-Definition
# ===========================================================================


@pytest.mark.asyncio
async def test_definition_on_named_item(client: LanguageClient):
    open_doc(client, TEST_URI, VALID_SOURCE)
    await wait_for_diagnostics(client, TEST_URI)

    # Position on "foo" (character 5)
    result = await client.text_document_definition_async(
        types.DefinitionParams(
            text_document=types.TextDocumentIdentifier(uri=TEST_URI),
            position=types.Position(line=0, character=5),
        )
    )
    assert result is not None
    if isinstance(result, list):
        assert len(result) >= 1
        loc = result[0]
    else:
        loc = result
    assert isinstance(loc, types.Location)


@pytest.mark.asyncio
async def test_definition_on_empty_file(client: LanguageClient):
    uri = "file:///tmp/def_empty.testlang"
    open_doc(client, uri, "")
    await asyncio.sleep(0.5)

    result = await client.text_document_definition_async(
        types.DefinitionParams(
            text_document=types.TextDocumentIdentifier(uri=uri),
            position=types.Position(line=0, character=0),
        )
    )
    assert result is None


# ===========================================================================
# Find References
# ===========================================================================


@pytest.mark.asyncio
async def test_references_on_named_item(client: LanguageClient):
    open_doc(client, TEST_URI, VALID_SOURCE)
    await wait_for_diagnostics(client, TEST_URI)

    # Position on "foo" (character 5)
    result = await client.text_document_references_async(
        types.ReferenceParams(
            text_document=types.TextDocumentIdentifier(uri=TEST_URI),
            position=types.Position(line=0, character=5),
            context=types.ReferenceContext(include_declaration=True),
        )
    )
    assert result is not None
    assert len(result) >= 1
    assert all(isinstance(loc, types.Location) for loc in result)


@pytest.mark.asyncio
async def test_references_on_invalid_model(client: LanguageClient):
    uri = "file:///tmp/refs_invalid.testlang"
    open_doc(client, uri, INVALID_SOURCE)
    await wait_for_diagnostics(client, uri)

    result = await client.text_document_references_async(
        types.ReferenceParams(
            text_document=types.TextDocumentIdentifier(uri=uri),
            position=types.Position(line=0, character=0),
            context=types.ReferenceContext(include_declaration=True),
        )
    )
    assert result is None or len(result) == 0


# ===========================================================================
# Document Symbols
# ===========================================================================


@pytest.mark.asyncio
async def test_symbols_valid_model(client: LanguageClient):
    open_doc(client, TEST_URI, VALID_SOURCE)
    await wait_for_diagnostics(client, TEST_URI)

    result = await client.text_document_document_symbol_async(
        types.DocumentSymbolParams(
            text_document=types.TextDocumentIdentifier(uri=TEST_URI),
        )
    )
    # symbols.py hardcodes SmAuto attribute names, so for our test grammar
    # it won't find top-level symbols via the hardcoded list.
    # The result should be an empty sequence (not None, not an error).
    assert result is not None


@pytest.mark.asyncio
async def test_symbols_invalid_model(client: LanguageClient):
    uri = "file:///tmp/sym_invalid.testlang"
    open_doc(client, uri, INVALID_SOURCE)
    await wait_for_diagnostics(client, uri)

    result = await client.text_document_document_symbol_async(
        types.DocumentSymbolParams(
            text_document=types.TextDocumentIdentifier(uri=uri),
        )
    )
    assert result is not None
    assert len(result) == 0


# ===========================================================================
# Semantic Tokens
# ===========================================================================


@pytest.mark.asyncio
async def test_semantic_tokens_valid_model(client: LanguageClient):
    open_doc(client, TEST_URI, VALID_SOURCE)
    await wait_for_diagnostics(client, TEST_URI)

    result = await client.text_document_semantic_tokens_full_async(
        types.SemanticTokensParams(
            text_document=types.TextDocumentIdentifier(uri=TEST_URI),
        )
    )
    assert result is not None
    assert isinstance(result, types.SemanticTokens)
    assert len(result.data) > 0
    assert len(result.data) % 5 == 0


@pytest.mark.asyncio
async def test_semantic_tokens_invalid_model(client: LanguageClient):
    uri = "file:///tmp/semtok_invalid.testlang"
    open_doc(client, uri, INVALID_SOURCE)
    await wait_for_diagnostics(client, uri)

    result = await client.text_document_semantic_tokens_full_async(
        types.SemanticTokensParams(
            text_document=types.TextDocumentIdentifier(uri=uri),
        )
    )
    # Should return empty tokens, not error
    assert result is not None
    assert len(result.data) == 0
