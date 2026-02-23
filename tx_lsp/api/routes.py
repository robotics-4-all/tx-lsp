"""REST API route handlers — reuses the same infrastructure as the LSP."""

import logging
import os
import tempfile

from fastapi import APIRouter, HTTPException, UploadFile
from lsprotocol import types as lsp_types

from tx_lsp.api.models import (
    ArtifactItem,
    CompletionItem,
    CompletionsResponse,
    DiagnosticItem,
    GenerateResponse,
    GeneratorInfo,
    GeneratorsResponse,
    HoverResponse,
    ModelPayload,
    PositionPayload,
    SymbolItem,
    SymbolsResponse,
    ValidateResponse,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

# These get set by app.py when creating the FastAPI app
_registry = None
_model_manager = None


def init_routes(registry, model_manager):
    global _registry, _model_manager
    _registry = registry
    _model_manager = model_manager


def _resolve_language(payload: ModelPayload):
    """Resolve the language from payload, raising 400 if not found."""
    if payload.language:
        langs = {lang.name: lang for lang in _registry.all_languages()}
        lang = langs.get(payload.language)
        if lang is None:
            raise HTTPException(400, f"Unknown language: {payload.language}")
        return lang

    if payload.filename:
        lang = _registry.language_for_file(payload.filename)
        if lang:
            return lang

    raise HTTPException(400, "Provide 'language' or a 'filename' with a recognized extension")


def _parse_model(payload: ModelPayload):
    """Parse a model from the payload, return the ModelState."""
    _resolve_language(payload)
    filename = payload.filename or "model.tmp"
    uri = f"file:///tmp/{filename}"
    return _model_manager.parse_document(uri, payload.source)


# ── Endpoints ──────────────────────────────────────────────────


@router.post("/validate", response_model=ValidateResponse)
def validate(payload: ModelPayload):
    state = _parse_model(payload)
    if state is None:
        raise HTTPException(400, "Could not parse model")

    diagnostics = []
    for d in state.diagnostics:
        severity_map = {
            lsp_types.DiagnosticSeverity.Error: "error",
            lsp_types.DiagnosticSeverity.Warning: "warning",
            lsp_types.DiagnosticSeverity.Information: "info",
            lsp_types.DiagnosticSeverity.Hint: "hint",
        }
        diagnostics.append(
            DiagnosticItem(
                line=d.range.start.line,
                character=d.range.start.character,
                end_line=d.range.end.line,
                end_character=d.range.end.character,
                severity=severity_map.get(d.severity, "error"),
                message=d.message,
                source=d.source or "tx-lsp",
            )
        )

    return ValidateResponse(valid=state.is_valid, diagnostics=diagnostics)


@router.post("/symbols", response_model=SymbolsResponse)
def symbols(payload: ModelPayload):
    state = _parse_model(payload)
    if state is None or state.model is None:
        return SymbolsResponse(symbols=[])

    from tx_lsp.features.symbols import get_document_symbols

    class MockLS:
        pass

    ls = MockLS()
    ls.model_manager = _model_manager

    filename = payload.filename or "model.tmp"
    uri = f"file:///tmp/{filename}"
    lsp_symbols = get_document_symbols(ls, uri)

    return SymbolsResponse(symbols=[_convert_symbol(s) for s in lsp_symbols])


def _convert_symbol(sym):
    """Convert an LSP DocumentSymbol to our API SymbolItem."""
    return SymbolItem(
        name=sym.name,
        kind=sym.kind.name,
        type=sym.detail or "",
        start_line=sym.range.start.line,
        start_character=sym.range.start.character,
        end_line=sym.range.end.line,
        end_character=sym.range.end.character,
        children=[_convert_symbol(c) for c in (sym.children or [])],
    )


@router.post("/completions", response_model=CompletionsResponse)
def completions(payload: PositionPayload):
    state = _parse_model(payload)
    if state is None or state.model is None:
        return CompletionsResponse(items=[])

    from tx_lsp.features.completion import _get_reference_completions

    items = _get_reference_completions(state.model, "")
    return CompletionsResponse(
        items=[
            CompletionItem(
                label=item.label,
                kind=item.kind.name if item.kind else "Text",
                detail=item.detail or "",
            )
            for item in items
        ]
    )


@router.post("/hover", response_model=HoverResponse)
def hover(payload: PositionPayload):
    state = _parse_model(payload)
    if state is None or state.model is None:
        raise HTTPException(404, "No model available")

    from tx_lsp.features.hover import get_hover_info

    class MockLS:
        pass

    ls = MockLS()
    ls.model_manager = _model_manager

    filename = payload.filename or "model.tmp"
    uri = f"file:///tmp/{filename}"
    position = lsp_types.Position(line=payload.line, character=payload.character)
    result = get_hover_info(ls, uri, position)

    if result is None:
        raise HTTPException(404, "No hover information at this position")

    return HoverResponse(content=result.contents.value)


@router.get("/generators", response_model=GeneratorsResponse)
def list_generators():
    try:
        from textx import generator_descriptions

        generators = []
        for lang_name, gens in generator_descriptions().items():
            for target_name, gen_desc in gens.items():
                generators.append(
                    GeneratorInfo(
                        language=gen_desc.language,
                        target=gen_desc.target,
                        description=gen_desc.description or "",
                    )
                )
        return GeneratorsResponse(generators=generators)
    except Exception as e:
        log.error("Failed to list generators: %s", e)
        return GeneratorsResponse(generators=[])


@router.post("/generate/{generator_target}", response_model=GenerateResponse)
def generate(generator_target: str, payload: ModelPayload):
    lang = _resolve_language(payload)

    try:
        from textx import generator_descriptions

        gens = generator_descriptions()
    except Exception as e:
        raise HTTPException(500, f"Failed to load generators: {e}")

    # Find the generator: check language-specific first, then 'any'
    gen_desc = None
    lang_gens = gens.get(lang.name, {})
    if generator_target in lang_gens:
        gen_desc = lang_gens[generator_target]
    elif "any" in gens and generator_target in gens["any"]:
        gen_desc = gens["any"][generator_target]

    if gen_desc is None:
        available = []
        for ln, gs in gens.items():
            for tn in gs:
                available.append(f"{ln}/{tn}")
        raise HTTPException(
            404,
            f"Generator '{generator_target}' not found for language '{lang.name}'. "
            f"Available: {', '.join(available)}",
        )

    # Parse the model
    state = _parse_model(payload)
    if state is None or state.model is None:
        raise HTTPException(400, "Model has errors — validate first")

    # Run generator into a temp directory and collect artifacts
    with tempfile.TemporaryDirectory(prefix="txlsp_gen_") as tmpdir:
        try:
            metamodel = lang.get_metamodel()
            gen_desc.generator(metamodel, state.model, tmpdir, overwrite=True, debug=False)
        except Exception as e:
            raise HTTPException(500, f"Generator failed: {e}")

        artifacts = []
        for root, _, files in os.walk(tmpdir):
            for fname in files:
                fpath = os.path.join(root, fname)
                with open(fpath) as f:
                    content = f.read()
                rel_path = os.path.relpath(fpath, tmpdir)
                artifacts.append(ArtifactItem(filename=rel_path, content=content))

    return GenerateResponse(artifacts=artifacts)


async def _read_upload(file: UploadFile, language: str | None = None):
    content = await file.read()
    source = content.decode("utf-8")
    filename = file.filename or "model.tmp"
    return ModelPayload(source=source, language=language, filename=filename)


@router.post("/validate/file", response_model=ValidateResponse)
async def validate_file(file: UploadFile, language: str | None = None):
    payload = await _read_upload(file, language)
    return validate(payload)


@router.post("/generate/{generator_target}/file", response_model=GenerateResponse)
async def generate_file(generator_target: str, file: UploadFile, language: str | None = None):
    payload = await _read_upload(file, language)
    return generate(generator_target, payload)
