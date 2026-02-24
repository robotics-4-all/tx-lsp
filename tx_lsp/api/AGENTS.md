# API — Rosetta-Compatible REST API Layer

## OVERVIEW

FastAPI HTTP interface implementing the rosetta Backend API Contract. Reuses `LanguageRegistry` + `ModelManager` from the LSP server. Optional dependency: `pip install tx-lsp[api]`.

## STRUCTURE

| File | Role |
|------|------|
| `app.py` | FastAPI app factory, API key auth (Security dependency), route mounting |
| `routes.py` | `public_router` (no auth: `/info`, `/capabilities`, `/health`) + `router` (auth: operations + file upload) |
| `models.py` | Pydantic models matching rosetta contract (LSP-compatible `Position`, `Range`, `Diagnostic`) |

## CONVENTIONS

- No URL prefix — endpoints at root level (rosetta contract requirement)
- Language resolution: from `uri` file extension → single-language fallback → 400 error
- Errors via `raise HTTPException(status_code, detail)`
- API key auth: optional, via FastAPI `Security(APIKeyHeader)` — only on operation endpoints, not `/health`/`/info`/`/capabilities`

## ENDPOINTS

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/info` | DSL metadata (name, version, file extensions) | No |
| GET | `/capabilities` | Supported operations | No |
| GET | `/health` | Liveness check | No |
| POST | `/validate` | Validate model, return diagnostics | Yes |
| POST | `/generate` | Run code generation (target in body) | Yes |
| POST | `/complete` | Completion suggestions at position | Yes |
| POST | `/hover` | Hover info at position | Yes |
| POST | `/validate/file` | Validate via file upload | Yes |
| POST | `/generate/file` | Generate via file upload | Yes |

## ANTI-PATTERNS

- Module globals (`_registry`, `_model_manager`) set by `init_routes()` — not thread-safe for multi-worker deployments.
- `_parse_source()` uses hardcoded `file:///tmp/` URI prefix — may conflict across concurrent requests.
