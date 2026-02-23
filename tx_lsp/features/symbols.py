"""Document Symbols feature — outline view of model structure.

Walks the parsed textX model and produces an LSP DocumentSymbol tree
representing the top-level elements (brokers, entities, automations, etc.).
"""

import logging

from lsprotocol import types

from tx_lsp.utils import textx_pos_to_lsp_range

log = logging.getLogger(__name__)

# Map textX class names to LSP SymbolKind for common DSL concepts
_SYMBOL_KINDS = {
    "Automation": types.SymbolKind.Function,
    "Entity": types.SymbolKind.Class,
    "MQTTBroker": types.SymbolKind.Module,
    "AMQPBroker": types.SymbolKind.Module,
    "RedisBroker": types.SymbolKind.Module,
    "Metadata": types.SymbolKind.Package,
    "RTMonitor": types.SymbolKind.Event,
}


def _get_symbol_kind(obj):
    """Determine the LSP SymbolKind for a textX model object."""
    cls_name = obj.__class__.__name__
    return _SYMBOL_KINDS.get(cls_name, types.SymbolKind.Variable)


def _get_symbol_name(obj):
    """Extract a display name from a textX model object."""
    if hasattr(obj, "name") and obj.name:
        return obj.name
    return obj.__class__.__name__


def _make_symbol(obj, source, children=None):
    """Create an LSP DocumentSymbol from a textX model object."""
    range_ = textx_pos_to_lsp_range(obj, source=source)
    if range_ is None:
        return None

    name = _get_symbol_name(obj)
    kind = _get_symbol_kind(obj)
    detail = obj.__class__.__name__

    return types.DocumentSymbol(
        name=name,
        kind=kind,
        range=range_,
        selection_range=range_,
        detail=detail,
        children=children or [],
    )


def get_document_symbols(ls, uri):
    """Build the DocumentSymbol tree for a parsed document.

    Returns a list of top-level DocumentSymbol objects.
    """
    state = ls.model_manager.get_state(uri)
    if state is None or state.model is None:
        return []

    model = state.model
    source = state.source
    symbols = []

    for attr_name in ("metadata", "monitor", "brokers", "entities", "automations"):
        value = getattr(model, attr_name, None)
        if value is None:
            continue

        if isinstance(value, list):
            for item in value:
                sym = _make_symbol(item, source, children=_get_children_symbols(item, source))
                if sym:
                    symbols.append(sym)
        else:
            sym = _make_symbol(value, source)
            if sym:
                symbols.append(sym)

    return symbols


def _get_children_symbols(obj, source):
    """Extract child symbols from a model object (e.g., Entity attributes)."""
    children = []

    if hasattr(obj, "attributes") and isinstance(getattr(obj, "attributes", None), list):
        for attr in obj.attributes:
            sym = _make_symbol(attr, source)
            if sym:
                children.append(sym)

    if hasattr(obj, "actions") and isinstance(getattr(obj, "actions", None), list):
        for action in obj.actions:
            sym = _make_symbol(action, source)
            if sym:
                children.append(sym)

    if hasattr(obj, "condition") and obj.condition is not None:
        sym = _make_symbol(obj.condition, source)
        if sym:
            children.append(sym)

    return children
