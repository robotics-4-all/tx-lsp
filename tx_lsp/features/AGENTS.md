# FEATURES — LSP Feature Implementations

## OVERVIEW

One module per LSP capability. All follow the same pattern: stateless function receiving `(ls, uri, position)`.

## PATTERN

Every feature module:
1. Public function called from `server.py` via `@server.feature()` decorator
2. Gets model state via `ls.model_manager.get_state(uri)`
3. Returns `None` or empty list on missing/invalid state
4. Private helpers prefixed with `_`
5. Uses `tx_lsp.utils` for position conversion and AST traversal

## WHERE TO LOOK

| Feature | File | Entry Function |
|---------|------|----------------|
| Diagnostics | `diagnostics.py` | `publish_diagnostics(ls, uri, source, version)` |
| Go-to-definition | `definition.py` | `goto_definition(ls, uri, position)` |
| Hover | `hover.py` | `get_hover_info(ls, uri, position)` |
| Completion | `completion.py` | `get_completions(ls, uri, position)` |
| Find references | `references.py` | `find_references(ls, uri, position, include_declaration)` |
| Document symbols | `symbols.py` | `get_document_symbols(ls, uri)` |

## ANTI-PATTERNS

- `completion.py` → `_get_reference_completions()` hardcodes SmAuto-specific attribute names (`brokers`, `entities`, `automations`). Should walk model generically.
- `symbols.py` → `get_document_symbols()` hardcodes top-level attribute names (`metadata`, `monitor`, `brokers`, `entities`, `automations`) and `_SYMBOL_KINDS` map. Not generic.
- `symbols.py` → `_get_children_symbols()` hardcodes `attributes`, `actions`, `condition`. Not generic.

## NOTES

- `diagnostics.py` is the only feature that triggers on document lifecycle (open/change/save). Others are on-demand.
- `definition.py` handles cross-file references via `_get_model_uri()` — checks `_tx_parser.file_name`.
- `hover.py` renders Markdown with grammar rule type + attribute listing.
