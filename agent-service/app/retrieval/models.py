from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SourceType = Literal["MARKDOWN", "PDF"]
RetrievalMode = Literal["lexical", "vector", "hybrid"]


class DocumentSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    section_key: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=500)
    source_locator: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=100_000, repr=False)


class PendingMetricChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    section_key: str
    section_title: str
    source_locator: str
    ordinal: int = Field(ge=0)
    content: str = Field(min_length=1, max_length=10_000, repr=False)
    embedding: tuple[float, ...] = Field(min_length=16, repr=False)


class StoredMetricDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    tenant_id: UUID
    title: str
    version: int = Field(ge=1)
    status: Literal["ACTIVE", "SUPERSEDED"]
    source_type: SourceType
    source_name: str
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_count: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime


class MetricChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    tenant_id: UUID
    document_id: UUID
    document_title: str
    document_version: int = Field(ge=1)
    section_key: str
    section_title: str
    source_locator: str
    ordinal: int = Field(ge=0)
    content: str = Field(min_length=1, repr=False)
    embedding: tuple[float, ...] = Field(min_length=16, repr=False)


class RankedChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk: MetricChunk
    score: float


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: UUID
    document_title: str
    document_version: int
    section_key: str
    section_title: str
    source_locator: str


class RetrievalHit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    content: str = Field(repr=False)
    citation: Citation
    lexical_score: float | None = None
    vector_score: float | None = None
    fused_score: float = Field(ge=0)


class RetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str = Field(min_length=1, max_length=4_000, repr=False)
    mode: RetrievalMode
    corpus_revision: str
    hits: tuple[RetrievalHit, ...]
    citations: tuple[Citation, ...]
    should_answer: bool
