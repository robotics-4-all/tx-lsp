"""Go-to-Definition feature — resolve cross-references to their definitions.

When the cursor is on a reference (e.g., 'home_broker' in 'broker: home_broker'),
this feature jumps to where that symbol is defined.

Uses textX's resolved cross-references and _tx_position metadata.
"""

import logging

from lsprotocol import types

from tx_lsp.utils import (
    get_object_at_position,
    textx_pos_to_lsp_range,
)

log = logging.getLogger(__name__)


def goto_definition(ls, uri, position):
    """Find the definition location for the symbol at the given position.

    Returns a Location or None.
    """
    state = ls.model_manager.get_state(uri)
    if state is None or state.model is None:
        return None

    model = state.model
    source = state.source

    # Find the object at cursor position
    obj = get_object_at_position(model, source, position.line, position.character)
    if obj is None:
        return None

    # If the object itself has a name and position, it might BE the definition.
    # We need to check if it's a reference to something else.
    target = _resolve_reference(obj, model)
    if target is None:
        return None

    range_ = textx_pos_to_lsp_range(target, source=source)
    if range_ is None:
        return None

    # Determine the URI for the target (could be in a different file)
    target_uri = _get_model_uri(target, uri)

    return types.Location(uri=target_uri, range=range_)


def _resolve_reference(obj, model):
    """Try to resolve a model object as a cross-reference.

    In textX, cross-references are resolved to the actual target object.
    If `obj` is a reference, it's already the target. We need to find
    the pattern: an attribute value that references a named object.

    Strategy: Walk the model looking for the same object instance
    appearing as an attribute value of another object. If found,
    the referenced object is the definition target.
    """
    # If obj has a 'name' attribute, it might be a definition itself.
    # Check if any parent has an attribute that references a named object
    # whose name matches. The object could be the reference target.

    # Simple heuristic: if the object has a 'name', check if something
    # else in the model refers to it — if so, this IS the definition.
    if hasattr(obj, "name") and obj.name:
        # This could be a reference resolved by textX — the obj IS the target
        return obj

    # For objects without names, check parent attributes
    if hasattr(obj, "parent") and obj.parent is not None:
        parent = obj.parent
        if hasattr(parent, "_tx_attrs"):
            for attr_name, attr_desc in parent._tx_attrs.items():
                val = getattr(parent, attr_name, None)
                if val is obj and hasattr(attr_desc, "ref") and attr_desc.ref:
                    # This attribute is a cross-reference — obj is already resolved
                    return obj

    return None


def _get_model_uri(obj, fallback_uri):
    """Determine the file URI for a model object.

    textX objects from imported files have a different _tx_parser
    with a different file_name.
    """
    if hasattr(obj, "_tx_parser") and obj._tx_parser:
        parser = obj._tx_parser
        if hasattr(parser, "file_name") and parser.file_name:
            return f"file://{parser.file_name}"
    return fallback_uri
