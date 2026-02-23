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
        from fastapi import Depends, FastAPI, HTTPException, Security
        from fastapi.security import APIKeyHeader
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

    dependencies = []
    if api_key:
        api_key_header = APIKeyHeader(name="X-API-Key")

        async def verify_api_key(key: str = Security(api_key_header)):
            if key != api_key:
                raise HTTPException(status_code=401, detail="Invalid or missing API key")

        dependencies = [Depends(verify_api_key)]

    app = FastAPI(
        title="tx-lsp API",
        description="Generic REST API for textX-based DSLs",
        version="0.1.0",
    )

    from tx_lsp.api.routes import init_routes, router

    init_routes(registry, model_manager)
    app.include_router(router, dependencies=dependencies)

    langs = registry.all_languages()
    log.info(
        "API ready with %d language(s): %s",
        len(langs),
        ", ".join(f"{lang.name} ({lang.pattern})" for lang in langs),
    )

    return app
