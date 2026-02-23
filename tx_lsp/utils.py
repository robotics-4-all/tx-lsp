"""Utility functions for position conversion and AST traversal."""

import logging
from fnmatch import fnmatch
from pathlib import Path

from lsprotocol import types

log = logging.getLogger(__name__)


def textx_pos_to_lsp_range(obj, source=None):
    """Convert textX _tx_position/_tx_position_end to an LSP Range.

    textX positions are 0-based character offsets into the source text.
    We need to convert them to (line, character) pairs.

    The source text can be provided directly, or extracted from the
    root model's _tx_parser if available.
    """
    if not hasattr(obj, "_tx_position") or not hasattr(obj, "_tx_position_end"):
        return None

    # Get source text: parameter > root model parser > object parser
    src = source
    if src is None and hasattr(obj, "_tx_parser") and hasattr(obj._tx_parser, "input"):
        src = obj._tx_parser.input
    if src is None:
        return None

    start_line, start_col = offset_to_line_col(src, obj._tx_position)
    end_line, end_col = offset_to_line_col(src, obj._tx_position_end)

    return types.Range(
        start=types.Position(line=start_line, character=start_col),
        end=types.Position(line=end_line, character=end_col),
    )


def offset_to_line_col(source, offset):
    """Convert a 0-based character offset to (line, col), both 0-based."""
    line = source[:offset].count("\n")
    last_nl = source[:offset].rfind("\n")
    col = offset - (last_nl + 1)
    return line, col


def line_col_to_offset(source, line, col):
    """Convert 0-based (line, col) to a 0-based character offset."""
    lines = source.split("\n")
    offset = sum(len(lines[i]) + 1 for i in range(line))  # +1 for \n
    return offset + col


def uri_to_path(uri):
    """Convert a file:// URI to a filesystem path."""
    if uri.startswith("file://"):
        return uri[7:]
    return uri


def path_matches_pattern(filepath, pattern):
    """Check if a file path matches a glob pattern (e.g., '*.auto')."""
    return fnmatch(Path(filepath).name, pattern)


def walk_model(obj, visited=None):
    """Recursively walk a textX model tree, yielding all model objects.

    Each yielded item is a (obj, parent) tuple.
    """
    if visited is None:
        visited = set()

    obj_id = id(obj)
    if obj_id in visited:
        return
    visited.add(obj_id)

    yield obj

    # Walk attributes that are model objects
    if hasattr(obj, "_tx_attrs"):
        for attr_name, attr_desc in obj._tx_attrs.items():
            value = getattr(obj, attr_name, None)
            if value is None:
                continue
            if isinstance(value, list):
                for item in value:
                    if hasattr(item, "_tx_position"):
                        yield from walk_model(item, visited)
            elif hasattr(value, "_tx_position"):
                yield from walk_model(value, visited)


def get_object_at_position(model, source, line, col):
    """Find the most specific model object at a given (line, col) position.

    Returns the deepest nested object whose position range contains the given
    position, or None.
    """
    offset = line_col_to_offset(source, line, col)
    best = None
    best_span = float("inf")

    for obj in walk_model(model):
        if not hasattr(obj, "_tx_position") or not hasattr(obj, "_tx_position_end"):
            continue
        start = obj._tx_position
        end = obj._tx_position_end
        if start <= offset <= end:
            span = end - start
            if span < best_span:
                best = obj
                best_span = span

    return best
