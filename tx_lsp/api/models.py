"""Pydantic request/response models for the REST API."""

from typing import Optional

from pydantic import BaseModel, Field


# ── Request Models ─────────────────────────────────────────────


class ModelPayload(BaseModel):
    source: str = Field(..., description="Model source code")
    language: Optional[str] = Field(
        None, description="Language name (auto-detected from filename if omitted)"
    )
    filename: Optional[str] = Field(
        None, description="Filename for import resolution and language detection"
    )


class PositionPayload(ModelPayload):
    line: int = Field(..., description="Cursor line (0-based)")
    character: int = Field(..., description="Cursor character (0-based)")


# ── Response Models ────────────────────────────────────────────


class DiagnosticItem(BaseModel):
    line: int
    character: int
    end_line: int
    end_character: int
    severity: str
    message: str
    source: str = "tx-lsp"


class ValidateResponse(BaseModel):
    valid: bool
    diagnostics: list[DiagnosticItem] = []


class SymbolItem(BaseModel):
    name: str
    kind: str
    type: str
    start_line: int
    start_character: int
    end_line: int
    end_character: int
    children: list["SymbolItem"] = []


class SymbolsResponse(BaseModel):
    symbols: list[SymbolItem] = []


class CompletionItem(BaseModel):
    label: str
    kind: str
    detail: str = ""


class CompletionsResponse(BaseModel):
    items: list[CompletionItem] = []


class HoverResponse(BaseModel):
    content: str


class GeneratorInfo(BaseModel):
    language: str
    target: str
    description: str = ""


class GeneratorsResponse(BaseModel):
    generators: list[GeneratorInfo] = []


class ArtifactItem(BaseModel):
    filename: str
    content: str


class GenerateResponse(BaseModel):
    artifacts: list[ArtifactItem] = []
