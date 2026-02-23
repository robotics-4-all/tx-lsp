"""Hover feature — show information about the element under the cursor.

Displays the textX rule type, attributes, and other metadata
for the model element at the hover position.
"""

import logging

from lsprotocol import types

from tx_lsp.utils import get_object_at_position

log = logging.getLogger(__name__)


def get_hover_info(ls, uri, position):
    """Get hover information for the element at the given position.

    Returns a Hover object or None.
    """
    state = ls.model_manager.get_state(uri)
    if state is None or state.model is None:
        return None

    obj = get_object_at_position(state.model, state.source, position.line, position.character)
    if obj is None:
        return None

    content = _build_hover_content(obj)
    if not content:
        return None

    return types.Hover(
        contents=types.MarkupContent(
            kind=types.MarkupKind.Markdown,
            value=content,
        )
    )


def _build_hover_content(obj):
    """Build Markdown hover content for a textX model object."""
    cls_name = obj.__class__.__name__
    parts = [f"**{cls_name}**"]

    # Show the name if the object has one
    if hasattr(obj, "name") and obj.name:
        parts[0] = f"**{cls_name}** `{obj.name}`"

    # Show attributes from the grammar rule
    if hasattr(obj, "_tx_attrs") and obj._tx_attrs:
        attr_lines = []
        for attr_name, attr_desc in obj._tx_attrs.items():
            value = getattr(obj, attr_name, None)
            # Skip parent reference and internal attributes
            if attr_name.startswith("_") or attr_name == "parent":
                continue
            type_name = _get_attr_type_name(attr_desc)
            if (
                value is not None
                and not isinstance(value, list)
                and not hasattr(value, "_tx_attrs")
            ):
                attr_lines.append(f"- `{attr_name}`: {type_name} = `{value}`")
            elif isinstance(value, list):
                attr_lines.append(f"- `{attr_name}`: {type_name}[{len(value)}]")
            else:
                attr_lines.append(f"- `{attr_name}`: {type_name}")

        if attr_lines:
            parts.append("\n**Attributes:**\n")
            parts.extend(attr_lines)

    return "\n".join(parts)


def _get_attr_type_name(attr_desc):
    """Extract a human-readable type name from a textX attribute descriptor."""
    if hasattr(attr_desc, "cls") and attr_desc.cls:
        cls = attr_desc.cls
        if hasattr(cls, "__name__"):
            return cls.__name__
        return str(cls)
    return "unknown"
