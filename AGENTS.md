# PROJECT KNOWLEDGE BASE

**Generated:** 2025-02-23
**Commit:** df7e3c0
**Branch:** master

## OVERVIEW

Generic LSP server + optional REST API for any textX-based DSL. Auto-discovers installed textX languages via entry_points, provides diagnostics/completion/hover/definition/references/symbols. Built on pygls + lsprotocol.

## STRUCTURE

```
tx-lsp/
├── pyproject.toml          # Package config, CLI entry point, ruff settings
├── tx_lsp/
│   ├── __main__.py         # CLI dispatcher: LSP (stdio/tcp/ws) or REST API
│   ├── server.py           # TxLanguageServer (pygls subclass), feature registration
│   ├── discovery.py        # LanguageRegistry — auto-discovers textX languages
│   ├── workspace.py        # ModelManager — parse/cache textX models per document
│   ├── utils.py            # Position conversion (textX offset <-> LSP line/col), AST walker
│   ├── features/           # LSP feature implementations (one per file)
│   └── api/                # Optional FastAPI REST API (install with `pip install tx-lsp[api]`)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add new LSP feature | `tx_lsp/features/` | Follow existing pattern: function takes `(ls, uri, position)` |
| Add new API endpoint | `tx_lsp/api/routes.py` | Add route to `router`, request/response models in `models.py` |
| Support new file extension | `LanguageRegistry.register_extra_pattern()` or `--extra-pattern` CLI flag | |
| Change CLI args | `tx_lsp/__main__.py` | |
| Position/offset math | `tx_lsp/utils.py` | textX uses 0-based char offsets; LSP uses 0-based line/col |
| textX model traversal | `tx_lsp/utils.py` → `walk_model()`, `get_object_at_position()` | |
| Parse error → diagnostic | `tx_lsp/workspace.py` → `_textx_error_to_diagnostics()` | textX errors have 1-based line/col → convert to 0-based |

## KEY ARCHITECTURE

- **LanguageRegistry** (`discovery.py`): Discovers textX languages via `textx.language_descriptions()`. Lazily creates metamodels on first use.
- **ModelManager** (`workspace.py`): Caches `ModelState` per URI. Writes source to temp file in same dir for textX import resolution, then deletes.
- **TxLanguageServer** (`server.py`): Owns registry + model_manager. Features registered via `@server.feature()` decorators.
- **Features** (`features/`): Stateless functions. All access model state via `ls.model_manager.get_state(uri)`.

## CONVENTIONS

- **Line length**: 99 chars (ruff)
- **Logging**: `log = logging.getLogger(__name__)` at module top. Config in `__main__.py`.
- **No tests**: No test suite exists yet.
- **No CI/CD**: No pipeline configured.
- **No type checker**: No mypy/pyright configured.
- **Imports**: Absolute imports (`from tx_lsp.utils import ...`), never relative.
- **Feature functions**: Top-level public function + private helpers prefixed with `_`.
- **Docstrings**: Module-level + public functions. Google-ish style.

## ANTI-PATTERNS

- **Temp file writes**: `ModelManager.parse_document()` writes temp files to disk for textX import resolution. Must always `os.unlink()` in `finally`.
- **API MockLS**: `routes.py` uses `MockLS` class to fake the LSP server interface. Fragile — breaks if features access new `ls` attributes.
- **Hardcoded SmAuto attributes**: `completion.py` references `brokers`, `entities`, `automations` — SmAuto-specific, not generic. Same in `symbols.py` (`metadata`, `monitor`, `brokers`, `entities`, `automations`).
- **Module globals in routes**: `_registry` and `_model_manager` are module-level globals set by `init_routes()`. Not thread-safe.

## COMMANDS

```bash
# Install (editable)
pip install -e .
pip install -e ".[api]"    # with REST API deps

# Run LSP server
tx-lsp                              # stdio (for editors)
tx-lsp --tcp --port 2087            # TCP (for debugging)
tx-lsp --ws --port 2087             # WebSocket
tx-lsp --extra-pattern '*.auto=smauto'  # custom extension mapping

# Run REST API
tx-lsp --api --api-port 8080
tx-lsp --api --api-key SECRET       # with auth

# Lint
ruff check tx_lsp/
ruff format tx_lsp/
```

## NOTES

- `pyproject.toml` references `README.md` but the file doesn't exist.
- textX positions are 0-based char offsets; textX errors have 1-based line/col. Both need conversion for LSP (0-based line/col).
- Metamodels are lazily instantiated and cached in `LanguageInfo._metamodel`.
- Extra patterns (CLI `--extra-pattern`) take precedence over registered patterns in language lookup.
