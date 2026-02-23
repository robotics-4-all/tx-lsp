"""Workspace model management with caching and validation.

Manages the lifecycle of parsed textX models for open documents.
Handles model caching, re-parsing on changes, and multi-file imports.
"""

import logging
import tempfile
import os
from pathlib import Path

from lsprotocol import types
from textx.exceptions import TextXError

log = logging.getLogger(__name__)


class ModelState:
    """Holds the parsed state of a single document."""

    def __init__(self, uri, version=None):
        self.uri = uri
        self.version = version
        self.model = None
        self.diagnostics = []
        self.source = ""

    @property
    def is_valid(self):
        return self.model is not None and len(self.diagnostics) == 0


class ModelManager:
    """Manages textX model parsing and caching for workspace documents.

    Responsibilities:
    - Parse documents using the appropriate language's metamodel
    - Cache parsed models for fast lookup
    - Convert textX errors to LSP diagnostics
    - Handle temporary files for in-memory document content
    """

    def __init__(self, registry):
        self.registry = registry
        self._models = {}  # uri -> ModelState

    def get_state(self, uri):
        """Get the current model state for a URI."""
        return self._models.get(uri)

    def parse_document(self, uri, source, version=None):
        """Parse a document and return its ModelState.

        Creates/updates the cached ModelState for this URI.
        Returns the ModelState with either a valid model or diagnostics.
        """
        from tx_lsp.utils import uri_to_path

        filepath = uri_to_path(uri)

        lang = self.registry.language_for_file(filepath)
        if lang is None:
            log.debug("No language found for %s", filepath)
            return None

        state = ModelState(uri, version)
        state.source = source

        try:
            metamodel = lang.get_metamodel()
            # textX needs to read from a file for import resolution.
            # Write source to a temp file in the same directory so relative
            # imports resolve correctly.
            parent_dir = str(Path(filepath).parent)
            suffix = Path(filepath).suffix
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=suffix, dir=parent_dir, delete=False, prefix=".txlsp_"
            ) as tmp:
                tmp.write(source)
                tmp_path = tmp.name

            try:
                model = metamodel.model_from_file(tmp_path)
                state.model = model
                log.debug("Successfully parsed %s", filepath)
            finally:
                os.unlink(tmp_path)

        except TextXError as e:
            state.diagnostics = self._textx_error_to_diagnostics(e)
            log.debug("Parse error in %s: %s", filepath, e)
        except Exception as e:
            # Catch-all for unexpected errors — still report as diagnostic
            state.diagnostics = [
                types.Diagnostic(
                    range=types.Range(
                        start=types.Position(line=0, character=0),
                        end=types.Position(line=0, character=0),
                    ),
                    message=str(e),
                    severity=types.DiagnosticSeverity.Error,
                    source="tx-lsp",
                )
            ]
            log.debug("Unexpected error parsing %s: %s", filepath, e)

        self._models[uri] = state
        return state

    def remove_document(self, uri):
        """Remove cached state for a closed document."""
        self._models.pop(uri, None)

    def _textx_error_to_diagnostics(self, error):
        """Convert a TextXError (syntax or semantic) to LSP Diagnostics."""
        diagnostics = []

        # textX errors have .line and .col (1-based)
        line = getattr(error, "line", 1) - 1  # to 0-based
        col = getattr(error, "col", 1) - 1

        # Determine severity based on error type
        severity = types.DiagnosticSeverity.Error

        diagnostics.append(
            types.Diagnostic(
                range=types.Range(
                    start=types.Position(line=max(0, line), character=max(0, col)),
                    end=types.Position(line=max(0, line), character=max(0, col + 1)),
                ),
                message=str(error),
                severity=severity,
                source="tx-lsp",
            )
        )

        return diagnostics
