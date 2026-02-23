"""Completion feature — context-aware suggestions for textX DSLs.

Provides completion candidates based on:
1. Grammar keywords from the metamodel
2. Names of defined objects (for cross-reference fields)
3. Contextual suggestions based on cursor position
"""

import logging
import re

from lsprotocol import types

from tx_lsp.utils import uri_to_path

log = logging.getLogger(__name__)


def get_completions(ls, uri, position):
    """Compute completion items for the given position.

    Returns a CompletionList.
    """
    items = []

    # Get the document text and current line context
    doc = ls.workspace.get_text_document(uri)
    current_line = ""
    if position.line < len(doc.lines):
        current_line = doc.lines[position.line]

    # Determine the text before cursor on the current line
    prefix = current_line[: position.character].strip()

    filepath = uri_to_path(uri)
    lang = ls.registry.language_for_file(filepath)
    if lang is None:
        return types.CompletionList(is_incomplete=False, items=[])

    # 1. Keyword completions from the grammar
    items.extend(_get_keyword_completions(lang, prefix))

    # 2. Named object completions from the current model
    state = ls.model_manager.get_state(uri)
    if state and state.model:
        items.extend(_get_reference_completions(state.model, prefix))

    return types.CompletionList(is_incomplete=False, items=items)


def _get_keyword_completions(lang, prefix):
    """Extract keyword completions from the textX grammar/metamodel.

    Walks the grammar rules to find string matches (keywords).
    """
    items = []
    try:
        metamodel = lang.get_metamodel()
        keywords = _extract_keywords(metamodel)
        for kw in keywords:
            if prefix and not kw.lower().startswith(prefix.lower()):
                continue
            items.append(
                types.CompletionItem(
                    label=kw,
                    kind=types.CompletionItemKind.Keyword,
                    detail="keyword",
                    insert_text=kw,
                )
            )
    except Exception as e:
        log.debug("Failed to extract keywords: %s", e)

    return items


def _extract_keywords(metamodel):
    """Extract all keywords from a textX metamodel's grammar.

    textX stores grammar rules that contain string matches (keywords)
    like 'Broker', 'Entity', 'when', 'then', etc.
    """
    keywords = set()

    # Walk all grammar rules in the metamodel
    if not hasattr(metamodel, "_current_parser"):
        # Try to get keywords from the grammar model
        if hasattr(metamodel, "grammar_parser") and metamodel.grammar_parser:
            _collect_keywords_from_parser(metamodel.grammar_parser, keywords)
        # Fallback: collect rule names as potential keywords
        for cls_name in metamodel:
            if cls_name and not cls_name.startswith("_"):
                keywords.add(cls_name)

    return keywords


def _collect_keywords_from_parser(parser, keywords):
    """Collect string literal keywords from a textX parser's grammar."""
    # textX grammar models have rules with string matches
    # that serve as keywords in the DSL
    if hasattr(parser, "parser_model") and parser.parser_model:
        _walk_peg_model(parser.parser_model, keywords, visited=set())


def _walk_peg_model(node, keywords, visited):
    """Walk a PEG parser model to extract string match keywords."""
    node_id = id(node)
    if node_id in visited:
        return
    visited.add(node_id)

    # StrMatch nodes contain keyword strings
    cls_name = node.__class__.__name__
    if cls_name == "StrMatch":
        if hasattr(node, "to_match") and node.to_match:
            kw = node.to_match.strip()
            if kw and re.match(r"^[a-zA-Z_]\w*$", kw):
                keywords.add(kw)

    # Recursively walk child nodes
    if hasattr(node, "nodes") and node.nodes:
        for child in node.nodes:
            if child is not None:
                _walk_peg_model(child, keywords, visited)


def _get_reference_completions(model, prefix):
    """Get completion items from named objects in the current model.

    Provides names of brokers, entities, automations, etc. for
    cross-reference fields.
    """
    items = []
    seen_names = set()

    # Collect all named objects from top-level model attributes
    for attr_name in ("brokers", "entities", "automations"):
        obj_list = getattr(model, attr_name, None)
        if not isinstance(obj_list, list):
            continue
        for obj in obj_list:
            name = getattr(obj, "name", None)
            if name and name not in seen_names:
                seen_names.add(name)
                cls_name = obj.__class__.__name__
                items.append(
                    types.CompletionItem(
                        label=name,
                        kind=types.CompletionItemKind.Reference,
                        detail=cls_name,
                        insert_text=name,
                    )
                )

    # Also collect attribute names for dot-completion (entity.attr)
    if "." in prefix:
        entity_name = prefix.split(".")[0].strip()
        for entity in getattr(model, "entities", []):
            if getattr(entity, "name", None) == entity_name:
                for attr in getattr(entity, "attributes", []):
                    attr_name = getattr(attr, "name", None)
                    if attr_name and attr_name not in seen_names:
                        seen_names.add(attr_name)
                        items.append(
                            types.CompletionItem(
                                label=attr_name,
                                kind=types.CompletionItemKind.Field,
                                detail=f"{entity_name} attribute",
                                insert_text=attr_name,
                            )
                        )

    return items
