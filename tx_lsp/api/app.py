"""FastAPI application — optional REST API for tx-lsp.

Reuses the same LanguageRegistry and ModelManager infrastructure
as the LSP server, just exposed over HTTP instead of JSON-RPC.
"""

import logging
from typing import Optional

from tx_lsp.discovery import LanguageRegistry
from tx_lsp.workspace import ModelManager

log = logging.getLogger(__name__)


def create_app(
    extra_patterns: Optional[dict] = None,
    api_key: Optional[str] = None,
):
    """Create a FastAPI application with tx-lsp endpoints.

    Args:
        extra_patterns: Map of glob patterns to language names.
        api_key: Optional API key for authentication.
    """
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
    except ImportError:
        raise ImportError(
            "FastAPI is required for the REST API. Install with: pip install tx-lsp[api]"
        )

    registry = LanguageRegistry()
    registry.discover()
    if extra_patterns:
        for pattern, lang_name in extra_patterns.items():
            registry.register_extra_pattern(pattern, lang_name)

    model_manager = ModelManager(registry)

    app = FastAPI(
        title="tx-lsp API",
        description="Generic REST API for textX-based DSLs",
        version="0.1.0",
    )

    # API key middleware
    if api_key:

        @app.middleware("http")
        async def check_api_key(request: Request, call_next):
            if request.url.path.startswith("/api/"):
                key = request.headers.get("X-API-Key")
                if key != api_key:
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid or missing API key"},
                    )
            return await call_next(request)

    from tx_lsp.api.routes import init_routes, router

    init_routes(registry, model_manager)
    app.include_router(router)

    langs = registry.all_languages()
    log.info(
        "API ready with %d language(s): %s",
        len(langs),
        ", ".join(f"{lang.name} ({lang.pattern})" for lang in langs),
    )

    return app
