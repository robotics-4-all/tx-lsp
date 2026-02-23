"""Find References feature — locate all usages of a symbol.

Walks the entire model AST to find all cross-references that
resolve to the same named object.
"""

import logging

from lsprotocol import types

from tx_lsp.utils import (
    get_object_at_position,
    textx_pos_to_lsp_range,
    walk_model,
)

log = logging.getLogger(__name__)


def find_references(ls, uri, position, include_declaration=True):
    """Find all references to the symbol at the given position.

    Returns a list of Location objects.
    """
    state = ls.model_manager.get_state(uri)
    if state is None or state.model is None:
        return []

    model = state.model
    source = state.source

    # Find the object at cursor position
    target = get_object_at_position(model, source, position.line, position.character)
    if target is None:
        return []

    # If target doesn't have a name, we can't find references to it
    if not hasattr(target, "name") or not target.name:
        return []

    target_name = target.name
    target_class = target.__class__.__name__
    locations = []

    # Walk the entire model looking for references to this object
    for obj in walk_model(model):
        if not hasattr(obj, "_tx_attrs"):
            continue

        for attr_name, attr_desc in obj._tx_attrs.items():
            value = getattr(obj, attr_name, None)
            if value is None:
                continue

            refs_to_check = value if isinstance(value, list) else [value]
            for ref in refs_to_check:
                if ref is target or (
                    hasattr(ref, "name")
                    and ref.name == target_name
                    and ref.__class__.__name__ == target_class
                ):
                    # Found a reference — get its position
                    if not include_declaration and ref is target:
                        continue
                    range_ = textx_pos_to_lsp_range(ref, source=source)
                    if range_:
                        ref_uri = _get_ref_uri(ref, uri)
                        locations.append(types.Location(uri=ref_uri, range=range_))

    return locations


def _get_ref_uri(obj, fallback_uri):
    """Determine the file URI for a referenced object."""
    if hasattr(obj, "_tx_parser") and obj._tx_parser:
        parser = obj._tx_parser
        if hasattr(parser, "file_name") and parser.file_name:
            return f"file://{parser.file_name}"
    return fallback_uri
