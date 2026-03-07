#!/usr/bin/env python
"""Standalone server for LSP integration tests.

Registers a test textX language, then starts tx-lsp in stdio mode.
This script is spawned by pytest-lsp as the server_command.
"""

import logging
import sys

from textx import metamodel_from_str, register_language

GRAMMAR = "Model: items+=Item; Item: 'item' name=ID '{' value=INT '}';"


def _make_metamodel():
    return metamodel_from_str(GRAMMAR)


# Register BEFORE the server discovers languages
register_language(
    "testlang",
    pattern="*.testlang",
    description="Test language for LSP integration tests",
    metamodel=_make_metamodel,
)

# Configure logging to stderr so it doesn't interfere with stdio LSP
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)

from tx_lsp.server import create_server

server = create_server()
server.start_io()
