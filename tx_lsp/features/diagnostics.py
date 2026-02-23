"""Diagnostics feature — parse errors and semantic validation.

Validates documents by attempting to build a textX model.
Converts any TextXError into LSP Diagnostics with precise positions.
"""

import logging

from lsprotocol import types

log = logging.getLogger(__name__)


def publish_diagnostics(ls, uri, source, version=None):
    """Parse a document and publish its diagnostics.

    This is the main entry point called by document lifecycle handlers
    (didOpen, didChange, didSave).
    """
    state = ls.model_manager.parse_document(uri, source, version)
    if state is None:
        # No language matched — clear any previous diagnostics
        ls.text_document_publish_diagnostics(
            types.PublishDiagnosticsParams(uri=uri, diagnostics=[])
        )
        return

    ls.text_document_publish_diagnostics(
        types.PublishDiagnosticsParams(
            uri=uri,
            version=version,
            diagnostics=state.diagnostics,
        )
    )

    if state.is_valid:
        log.debug("Document valid: %s", uri)
    else:
        log.debug("Document has %d diagnostic(s): %s", len(state.diagnostics), uri)
