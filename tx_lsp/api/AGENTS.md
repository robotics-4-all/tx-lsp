# API — Optional REST API Layer

## OVERVIEW

FastAPI HTTP interface reusing the same `LanguageRegistry` + `ModelManager` as the LSP server. Optional dependency: `pip install tx-lsp[api]`.

## STRUCTURE

| File | Role |
|------|------|
| `app.py` | FastAPI app factory, API key middleware, route mounting |
| `routes.py` | Endpoint handlers under `/api/v1/` |
| `models.py` | Pydantic request/response schemas |

## CONVENTIONS

- All endpoints prefixed `/api/v1/`
- Language resolution: `payload.language` name or auto-detect from `payload.filename`
- Errors via `raise HTTPException(status_code, detail)`
- API key auth: optional, checked via `X-API-Key` header middleware

## ENDPOINTS

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/validate` | Parse model, return diagnostics |
| POST | `/api/v1/symbols` | Parse model, return document symbols |
| POST | `/api/v1/completions` | Return completion candidates |
| POST | `/api/v1/hover` | Return hover info at position |
| GET | `/api/v1/generators` | List installed textX generators |
| POST | `/api/v1/generate/{target}` | Run generator, return artifacts |

## ANTI-PATTERNS

- `routes.py` uses `MockLS` classes to bridge API calls to LSP feature functions. If a feature accesses a new `ls` attribute, the mock breaks silently.
- Module globals (`_registry`, `_model_manager`) set by `init_routes()` — not thread-safe for multi-worker deployments.
- `_parse_model()` uses hardcoded `file:///tmp/` URI prefix — may conflict across concurrent requests.
