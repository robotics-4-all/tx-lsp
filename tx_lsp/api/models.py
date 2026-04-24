"""Pydantic request/response models — rosetta Backend API Contract.

Follows LSP-compatible data structures to ensure compatibility
with the Rosetta DSL gateway (github.com/robotics-4-all/rosetta).
"""

from __future__ import annotations

from typing import Dict, List, Optional

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
    source: Optional[str] = None


class CompletionItem(BaseModel):
    """An LSP-compatible completion suggestion."""

    label: str
    kind: Optional[int] = None
    detail: Optional[str] = None
    documentation: Optional[str] = None
    insert_text: Optional[str] = None


# ── Info & Capabilities ────────────────────────────────────────


class DSLInfoResponse(BaseModel):
    """DSL metadata returned by GET /info."""

    name: str
    version: str = "0.0.0"
    file_extensions: List[str] = Field(default_factory=list)
    language_id: Optional[str] = None


class DSLCapabilities(BaseModel):
    """Supported operations returned by GET /capabilities."""

    validation: bool = False
    generation: bool = False
    completion: bool = False
    hover: bool = False
    formatting: bool = False
    goto_definition: bool = False
    find_references: bool = False
    generation_targets: List[str] = Field(default_factory=list)


# ── Request Models ─────────────────────────────────────────────


class ValidateRequest(BaseModel):
    """Request body for POST /validate."""

    source: str
    uri: Optional[str] = None
    language: Optional[str] = None


class GenerateRequest(BaseModel):
    """Request body for POST /generate."""

    source: str
    target: Optional[str] = None
    params: Dict[str, str] = Field(default_factory=dict)
    uri: Optional[str] = None
    language: Optional[str] = None


class CompletionRequest(BaseModel):
    """Request body for POST /complete."""

    source: str
    position: Position
    uri: Optional[str] = None
    language: Optional[str] = None


class HoverRequest(BaseModel):
    """Request body for POST /hover."""

    source: str
    position: Position
    uri: Optional[str] = None
    language: Optional[str] = None


# ── Response Models ────────────────────────────────────────────


class ValidateResponse(BaseModel):
    """Response from POST /validate."""

    valid: bool
    diagnostics: List[Diagnostic] = Field(default_factory=list)


class GenerateResponse(BaseModel):
    """Response from POST /generate."""

    artifacts: Dict[str, str] = Field(default_factory=dict)
    diagnostics: List[Diagnostic] = Field(default_factory=list)


class CompletionResponse(BaseModel):
    """Response from POST /complete."""

    items: List[CompletionItem] = Field(default_factory=list)


class HoverResponse(BaseModel):
    """Response from POST /hover."""

    content: Optional[str] = None
    range: Optional[Range] = None
