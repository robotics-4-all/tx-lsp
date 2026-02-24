"""Pydantic request/response models — rosetta Backend API Contract.

Follows LSP-compatible data structures to ensure compatibility
with the Rosetta DSL gateway (github.com/robotics-4-all/rosetta).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── LSP-compatible primitives ──────────────────────────────────


class Position(BaseModel):
    """Zero-based line/character position within a document."""

    line: int = Field(ge=0, description="Zero-based line number")
    character: int = Field(ge=0, description="Zero-based character offset")


class Range(BaseModel):
    """A range within a document defined by start and end positions."""

    start: Position
    end: Position


class Diagnostic(BaseModel):
    """An LSP-compatible diagnostic (error, warning, etc.)."""

    range: Range
    message: str
    severity: int = 1  # 1=Error, 2=Warning, 3=Info, 4=Hint
    source: str | None = None


class CompletionItem(BaseModel):
    """An LSP-compatible completion suggestion."""

    label: str
    kind: int | None = None
    detail: str | None = None
    documentation: str | None = None
    insert_text: str | None = None


# ── Info & Capabilities ────────────────────────────────────────


class DSLInfoResponse(BaseModel):
    """DSL metadata returned by GET /info."""

    name: str
    version: str = "0.0.0"
    file_extensions: list[str] = Field(default_factory=list)
    language_id: str | None = None


class DSLCapabilities(BaseModel):
    """Supported operations returned by GET /capabilities."""

    validation: bool = False
    generation: bool = False
    completion: bool = False
    hover: bool = False
    formatting: bool = False
    goto_definition: bool = False
    find_references: bool = False
    generation_targets: list[str] = Field(default_factory=list)


# ── Request Models ─────────────────────────────────────────────


class ValidateRequest(BaseModel):
    """Request body for POST /validate."""

    source: str
    uri: str | None = None


class GenerateRequest(BaseModel):
    """Request body for POST /generate."""

    source: str
    target: str | None = None
    params: dict[str, str] = Field(default_factory=dict)


class CompletionRequest(BaseModel):
    """Request body for POST /complete."""

    source: str
    position: Position
    uri: str | None = None


class HoverRequest(BaseModel):
    """Request body for POST /hover."""

    source: str
    position: Position
    uri: str | None = None


# ── Response Models ────────────────────────────────────────────


class ValidateResponse(BaseModel):
    """Response from POST /validate."""

    valid: bool
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class GenerateResponse(BaseModel):
    """Response from POST /generate."""

    artifacts: dict[str, str] = Field(default_factory=dict)
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class CompletionResponse(BaseModel):
    """Response from POST /complete."""

    items: list[CompletionItem] = Field(default_factory=list)


class HoverResponse(BaseModel):
    """Response from POST /hover."""

    content: str | None = None
    range: Range | None = None
