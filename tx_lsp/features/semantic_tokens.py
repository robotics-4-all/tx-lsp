"""Semantic tokens feature — syntax highlighting for textX DSLs.

Provides semantic tokens for:
1. Grammar keywords
2. Model object definitions (classes)
3. Cross-references (variables)
4. Literals (numbers, strings)
"""

import logging
import re

from lsprotocol import types

from tx_lsp.features.completion import _extract_keywords
from tx_lsp.utils import offset_to_line_col, walk_model

log = logging.getLogger(__name__)

TOKEN_TYPES = [
    "keyword",  # 0 — grammar keywords
    "class",  # 1 — named model object definitions
    "property",  # 2 — attribute names within objects
    "variable",  # 3 — cross-references to named objects
    "number",  # 4 — integer/float literal values
    "string",  # 5 — string literal values
    "type",  # 6 — type references
]

TOKEN_MODIFIERS = [
    "definition",  # 0 — marks where a symbol is defined
    "declaration",  # 1
]


def get_semantic_tokens(ls, uri):
    """Compute semantic tokens for the given document.

    Returns a SemanticTokens object.
    """
    state = ls.model_manager.get_state(uri)
    if state is None or state.model is None or state.source is None:
        return types.SemanticTokens(data=[])

    tokens = []

    # 1. Collect keyword tokens
    lang = ls.registry.language_for_file(uri)
    if lang is not None:
        try:
            metamodel = lang.get_metamodel()
            keywords = _extract_keywords(metamodel)
            tokens.extend(_collect_keyword_tokens(state.source, keywords))
        except Exception as e:
            log.debug("Failed to extract keywords for semantic tokens: %s", e)

    # 2. Collect model object tokens
    tokens.extend(_collect_model_tokens(state.model, state.source))

    # Sort tokens by line, then column
    tokens.sort(key=lambda t: (t[0], t[1]))

    # Deduplicate tokens by position (line, col)
    # If there are multiple tokens at the same position, keep the first one
    unique_tokens = []
    seen = set()
    for t in tokens:
        key = (t[0], t[1])
        if key not in seen:
            seen.add(key)
            unique_tokens.append(t)

    # Delta encode
    data = []
    prev_line = 0
    prev_col = 0

    for line, col, length, tok_type, tok_mod in unique_tokens:
        delta_line = line - prev_line
        delta_col = col - prev_col if delta_line == 0 else col
        data.extend([delta_line, delta_col, length, tok_type, tok_mod])
        prev_line = line
        prev_col = col

    return types.SemanticTokens(data=data)


def _collect_keyword_tokens(source, keywords):
    """Find occurrences of keywords in the source text."""
    tokens = []
    if not keywords:
        return tokens

    keyword_idx = TOKEN_TYPES.index("keyword")

    for kw in keywords:
        # Find all occurrences of the keyword as a standalone word
        # Escape the keyword to handle any special regex characters
        pattern = r"\b" + re.escape(kw) + r"\b"
        for match in re.finditer(pattern, source):
            start_offset = match.start()
            line, col = offset_to_line_col(source, start_offset)
            tokens.append((line, col, len(kw), keyword_idx, 0))

    return tokens


def _collect_model_tokens(model, source):
    """Walk the model and extract tokens for definitions, references, and literals."""
    tokens = []

    class_idx = TOKEN_TYPES.index("class")
    variable_idx = TOKEN_TYPES.index("variable")
    number_idx = TOKEN_TYPES.index("number")
    string_idx = TOKEN_TYPES.index("string")

    definition_mod = 1 << TOKEN_MODIFIERS.index("definition")

    for obj in walk_model(model):
        if not hasattr(obj, "_tx_position") or not hasattr(obj, "_tx_position_end"):
            continue

        start_offset = obj._tx_position
        end_offset = obj._tx_position_end
        obj_source = source[start_offset:end_offset]

        # Object definition (class)
        if hasattr(obj, "name") and isinstance(obj.name, str) and obj.name:
            name_pattern = r"\b" + re.escape(obj.name) + r"\b"
            match = re.search(name_pattern, obj_source)
            if match:
                name_offset = start_offset + match.start()
                line, col = offset_to_line_col(source, name_offset)
                tokens.append((line, col, len(obj.name), class_idx, definition_mod))

        # Attributes (literals and references)
        if hasattr(obj, "_tx_attrs"):
            for attr_name, attr_desc in obj._tx_attrs.items():
                value = getattr(obj, attr_name, None)
                if value is None:
                    continue

                values = value if isinstance(value, list) else [value]

                for val in values:
                    if (
                        attr_desc.ref
                        and not getattr(attr_desc, "cont", False)
                        and hasattr(val, "name")
                        and isinstance(val.name, str)
                        and val.name
                    ):
                        # Cross-reference
                        name_pattern = r"\b" + re.escape(val.name) + r"\b"
                        for match in re.finditer(name_pattern, obj_source):
                            # Skip if this is the definition we already found
                            if hasattr(obj, "name") and obj.name == val.name:
                                def_match = re.search(
                                    r"\b" + re.escape(obj.name) + r"\b", obj_source
                                )
                                if def_match and match.start() == def_match.start():
                                    continue
                            ref_offset = start_offset + match.start()
                            line, col = offset_to_line_col(source, ref_offset)
                            tokens.append((line, col, len(val.name), variable_idx, 0))

                    elif isinstance(val, str):
                        # String literal
                        str_pattern = r'["\']' + re.escape(val) + r'["\']'
                        for match in re.finditer(str_pattern, obj_source):
                            str_offset = start_offset + match.start()
                            line, col = offset_to_line_col(source, str_offset)
                            tokens.append((line, col, len(match.group(0)), string_idx, 0))

                    elif isinstance(val, (int, float)) and not isinstance(val, bool):
                        # Number literal
                        num_str = str(val)
                        num_pattern = r"\b" + re.escape(num_str) + r"\b"
                        for match in re.finditer(num_pattern, obj_source):
                            num_offset = start_offset + match.start()
                            line, col = offset_to_line_col(source, num_offset)
                            tokens.append((line, col, len(num_str), number_idx, 0))

    return tokens
