"""REST API route handlers — rosetta Backend API Contract.

Exposes endpoints that comply with the Rosetta DSL gateway's
Backend API Contract for validation, generation, completion, and hover.
"""

import logging
import os
import tempfile

from fastapi import APIRouter, HTTPException, UploadFile
from lsprotocol import types as lsp_types

from tx_lsp import __version__
from tx_lsp.api.models import (
    CompletionItem,
    CompletionRequest,
    CompletionResponse,
    Diagnostic,
    DSLCapabilities,
    DSLInfoResponse,
    GenerateRequest,
    GenerateResponse,
    HoverRequest,
    HoverResponse,
    Position,
    Range,
    ValidateRequest,
    ValidateResponse,
)

log = logging.getLogger(__name__)

# Public routes — no auth required (health, info, capabilities)
public_router = APIRouter()

# Protected routes — auth applied by app.py
router = APIRouter()

# Set by app.py during startup
_registry = None
_model_manager = None


def init_routes(registry, model_manager):
    global _registry, _model_manager
    _registry = registry
    _model_manager = model_manager


# ── Helpers ────────────────────────────────────────────────────

_TEXTX_BUILTIN_LANGS = {"textX"}
_TEXTX_BUILTIN_GEN_LANGS = {"textX", "textx", "any"}


def _dsl_languages():
    """Return only user-installed DSL languages, excluding textX builtins."""
    return [lang for lang in _registry.all_languages() if lang.name not in _TEXTX_BUILTIN_LANGS]


def _dsl_generators():
    """Return only user-installed generators, excluding textX builtins."""
    from textx import generator_descriptions

    dsl_gens = {}
    for lang_name, gens in generator_descriptions().items():
        if lang_name in _TEXTX_BUILTIN_GEN_LANGS:
            continue
        dsl_gens[lang_name] = gens
    return dsl_gens


def _resolve_language(uri=None, language=None):
    """Resolve language from explicit name, URI file extension, or fallback to primary DSL."""
    if language:
        lang = _registry.language_for_name(language)
        if lang is None:
            available = [l.name for l in _dsl_languages()]
            raise HTTPException(
                400,
                f"Unknown language '{language}'. Available: {', '.join(available)}",
            )
        return lang

    if uri:
        from tx_lsp.utils import uri_to_path

        filepath = uri_to_path(uri)
        lang = _registry.language_for_file(filepath)
        if lang:
            return lang

    langs = _dsl_languages()
    if not langs:
        raise HTTPException(503, "No textX DSL languages discovered")
    if len(langs) > 1:
        log.warning("Multiple languages available, defaulting to '%s'", langs[0].name)
    return langs[0]


def _default_extension(lang):
    """Get the primary file extension for a language (e.g. '.smauto')."""
    patterns = lang.pattern.split()
    if patterns:
        return patterns[0].replace("*", "")
    return ".tmp"


def _parse_source(source, uri=None, language=None):
    """Parse source text, resolve language, return (state, lang)."""
    lang = _resolve_language(uri, language)
    filename = f"model{_default_extension(lang)}"
    effective_uri = uri or f"file:///tmp/{filename}"
    state = _model_manager.parse_document(effective_uri, source)
    if state is None:
        raise HTTPException(400, "Failed to parse model")
    return state, lang


def _convert_diagnostic(d):
    """Convert an lsprotocol Diagnostic to a rosetta-compatible Diagnostic."""
    severity_map = {
        lsp_types.DiagnosticSeverity.Error: 1,
        lsp_types.DiagnosticSeverity.Warning: 2,
        lsp_types.DiagnosticSeverity.Information: 3,
        lsp_types.DiagnosticSeverity.Hint: 4,
    }
    return Diagnostic(
        range=Range(
            start=Position(line=d.range.start.line, character=d.range.start.character),
            end=Position(line=d.range.end.line, character=d.range.end.character),
        ),
        message=d.message,
        severity=severity_map.get(d.severity, 1),
        source=d.source,
    )


# ── Public Endpoints (no auth) ─────────────────────────────────


@public_router.get("/info", response_model=DSLInfoResponse)
def info():
    langs = _dsl_languages()
    if not langs:
        raise HTTPException(503, "No textX DSL languages discovered")

    primary = langs[0]

    extensions = []
    for lang in langs:
        for pat in lang.pattern.split():
            ext = pat.replace("*", "")
            if ext not in extensions:
                extensions.append(ext)
    for pat in _registry._extra_patterns:
        ext = pat.replace("*", "")
        if ext not in extensions:
            extensions.append(ext)

    return DSLInfoResponse(
        name=primary.name,
        version=__version__,
        file_extensions=extensions,
        language_id=primary.name,
    )


@public_router.get("/capabilities", response_model=DSLCapabilities)
def capabilities():
    caps = DSLCapabilities(validation=True, completion=True, hover=True)
    try:
        gens = _dsl_generators()
        targets = set()
        for lang_gens in gens.values():
            for target_name in lang_gens:
                targets.add(target_name)
        if targets:
            caps.generation = True
            caps.generation_targets = sorted(targets)
    except Exception:
        pass
    return caps


@public_router.get("/keywords")
def keywords():
    lang = _resolve_language()
    return _get_keyword_completions(lang)


@public_router.get("/health")
def health():
    return {"status": "healthy"}


# ── Contract Endpoints ─────────────────────────────────────────


@router.post("/validate", response_model=ValidateResponse)
def validate(body: ValidateRequest):
    state, _ = _parse_source(body.source, body.uri, body.language)
    diagnostics = [_convert_diagnostic(d) for d in state.diagnostics]
    return ValidateResponse(valid=state.is_valid, diagnostics=diagnostics)


@router.post("/generate", response_model=GenerateResponse)
def generate(body: GenerateRequest):
    state, lang = _parse_source(body.source, body.uri, body.language)

    if not body.target:
        raise HTTPException(400, "Generation target is required")

    if not state.is_valid:
        return GenerateResponse(
            artifacts={},
            diagnostics=[_convert_diagnostic(d) for d in state.diagnostics],
        )

    return _run_generation(state, lang, body.target)


@router.post("/complete", response_model=CompletionResponse)
def complete(body: CompletionRequest):
    lang = _resolve_language(body.uri, body.language)
    items = []

    items.extend(_get_keyword_completions(lang))

    filename = f"model{_default_extension(lang)}"
    uri = body.uri or f"file:///tmp/{filename}"
    state = _model_manager.parse_document(uri, body.source)
    if state and state.model:
        items.extend(_get_named_completions(state.model))

    return CompletionResponse(items=items)


@router.post("/hover", response_model=HoverResponse)
def hover(body: HoverRequest):
    state, _ = _parse_source(body.source, body.uri, body.language)

    if state.model is None:
        return HoverResponse()

    from tx_lsp.features.hover import _build_hover_content
    from tx_lsp.utils import get_object_at_position, textx_pos_to_lsp_range

    try:
        obj = get_object_at_position(
            state.model, state.source, body.position.line, body.position.character
        )
    except (IndexError, ValueError):
        return HoverResponse()
    if obj is None:
        return HoverResponse()

    content = _build_hover_content(obj)
    if not content:
        return HoverResponse()

    hover_range = None
    lsp_range = textx_pos_to_lsp_range(obj, source=state.source)
    if lsp_range:
        hover_range = Range(
            start=Position(line=lsp_range.start.line, character=lsp_range.start.character),
            end=Position(line=lsp_range.end.line, character=lsp_range.end.character),
        )

    return HoverResponse(content=content, range=hover_range)


# ── File Upload Endpoints ──────────────────────────────────────


async def _read_upload(file: UploadFile):
    content = await file.read()
    source = content.decode("utf-8")
    filename = file.filename or "model.tmp"
    uri = f"file:///tmp/{filename}"
    return source, uri


@router.post("/validate/file", response_model=ValidateResponse)
async def validate_file(file: UploadFile):
    source, uri = await _read_upload(file)
    return validate(ValidateRequest(source=source, uri=uri))


@router.post("/generate/file", response_model=GenerateResponse)
async def generate_file(file: UploadFile, target: str):
    source, uri = await _read_upload(file)
    state, lang = _parse_source(source, uri)

    if not state.is_valid:
        return GenerateResponse(
            artifacts={},
            diagnostics=[_convert_diagnostic(d) for d in state.diagnostics],
        )

    return _run_generation(state, lang, target)


# ── Generation Helper ──────────────────────────────────────────


def _run_generation(state, lang, target):
    try:
        gens = _dsl_generators()
    except Exception as e:
        raise HTTPException(500, f"Failed to load generators: {e}")

    gen_desc = None
    lang_gens = gens.get(lang.name, {})
    if target in lang_gens:
        gen_desc = lang_gens[target]

    if gen_desc is None:
        available = []
        for ln, gs in gens.items():
            for tn in gs:
                available.append(f"{ln}/{tn}")
        raise HTTPException(
            404,
            f"Generator '{target}' not found for language '{lang.name}'. "
            f"Available: {', '.join(available)}",
        )

    with tempfile.TemporaryDirectory(prefix="txlsp_gen_") as tmpdir:
        try:
            metamodel = lang.get_metamodel()
            gen_desc.generator(metamodel, state.model, tmpdir, overwrite=True, debug=False)
        except Exception as e:
            raise HTTPException(500, f"Generator failed: {e}")

        artifacts = {}
        for root, _, files in os.walk(tmpdir):
            for fname in files:
                fpath = os.path.join(root, fname)
                with open(fpath) as f:
                    content = f.read()
                rel_path = os.path.relpath(fpath, tmpdir)
                artifacts[rel_path] = content

    return GenerateResponse(artifacts=artifacts)


# ── Completion Helpers ─────────────────────────────────────────


def _get_keyword_completions(lang):
    from tx_lsp.features.completion import _extract_keywords

    items = []
    try:
        metamodel = lang.get_metamodel()
        keywords = _extract_keywords(metamodel)
        for kw in keywords:
            items.append(
                CompletionItem(
                    label=kw,
                    kind=14,  # CompletionItemKind.Keyword
                    detail="keyword",
                    insert_text=kw,
                )
            )
    except Exception as e:
        log.debug("Failed to extract keywords: %s", e)
    return items


def _get_named_completions(model):
    from tx_lsp.utils import walk_model

    items = []
    seen = set()
    for obj in walk_model(model):
        name = getattr(obj, "name", None)
        if name and name not in seen:
            seen.add(name)
            items.append(
                CompletionItem(
                    label=name,
                    kind=6,  # CompletionItemKind.Variable
                    detail=obj.__class__.__name__,
                    insert_text=name,
                )
            )
    return items
