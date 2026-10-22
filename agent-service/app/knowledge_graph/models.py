from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

EntityKind = Literal["Metric", "Table", "Column", "BusinessTerm", "Document", "DataSource"]
RelationKind = Literal[
    "DEFINED_IN", "DERIVED_FROM", "USES_COLUMN", "BELONGS_TO", "RELATED_TO", "JOINS_WITH"
]


class EntityDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    kind: EntityKind
    evidence: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0, le=1)


class RelationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1, max_length=80)
    target: str = Field(min_length=1, max_length=80)
    kind: RelationKind
    evidence: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0, le=1)


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entities: list[EntityDraft] = Field(max_length=100)
    relations: list[RelationDraft] = Field(max_length=200)

    @model_validator(mode="after")
    def validate_references(self):
        ids = [entity.id for entity in self.entities]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate entity id")
        names = [(e.kind, e.name.casefold()) for e in self.entities]
        if len(names) != len(set(names)):
            raise ValueError("duplicate entity name and kind")
        for relation in self.relations:
            if relation.source not in ids or relation.target not in ids:
                raise ValueError("relation refers to unknown entity")
        return self


class GraphNode(BaseModel):
    id: str
    name: str
    kind: EntityKind
    source_id: UUID
    source_name: str
    evidence: str
    confidence: float
    extracted_at: datetime


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    kind: RelationKind
    source_id: UUID
    source_name: str
    evidence: str
    confidence: float
    extracted_at: datetime


class Subgraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    truncated: bool = False


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: UUID
    source_name: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=20_000, repr=False)


class GraphQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(default="", max_length=4000)
    limit: int = Field(default=60, ge=1, le=100)
    depth: int = Field(default=1, ge=0, le=3)


class GraphAnswerDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=8000)
    citation_ids: list[str] = Field(max_length=30)


class GraphAnswer(BaseModel):
    answer: str
    citations: list[dict]
    graph: Subgraph
    should_answer: bool
