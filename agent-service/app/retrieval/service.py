import hashlib
from collections.abc import Sequence
from uuid import UUID

from app.retrieval.cache import RetrievalCache
from app.retrieval.embeddings import EmbeddingProvider, HashingEmbeddingProvider
from app.retrieval.models import (
    Citation,
    PendingMetricChunk,
    RankedChunk,
    RetrievalHit,
    RetrievalMode,
    RetrievalResult,
    SourceType,
    StoredMetricDocument,
)
from app.retrieval.parsing import chunk_sections, parse_document
from app.retrieval.repository import MetricKnowledgeRepository


class MetricRetrievalService:
    def __init__(
        self,
        *,
        repository: MetricKnowledgeRepository,
        embedding_provider: EmbeddingProvider | None = None,
        cache: RetrievalCache | None = None,
        chunk_max_characters: int = 1_200,
        chunk_overlap_characters: int = 120,
        default_limit: int = 5,
        rrf_k: int = 60,
        min_lexical_score: float = 0.08,
        min_vector_score: float = 0.26,
        max_markdown_bytes: int = 2_000_000,
        max_pdf_bytes: int = 10_000_000,
        max_pdf_pages: int = 100,
    ) -> None:
        if rrf_k <= 0:
            raise ValueError("rrf_k must be positive")
        if not 1 <= default_limit <= 20:
            raise ValueError("default_limit must be between 1 and 20")
        self._repository = repository
        self._embeddings = embedding_provider or HashingEmbeddingProvider()
        self._cache = cache or RetrievalCache()
        self._chunk_max_characters = chunk_max_characters
        self._chunk_overlap_characters = chunk_overlap_characters
        self._default_limit = default_limit
        self._rrf_k = rrf_k
        self._min_lexical_score = min_lexical_score
        self._min_vector_score = min_vector_score
        self._max_markdown_bytes = max_markdown_bytes
        self._max_pdf_bytes = max_pdf_bytes
        self._max_pdf_pages = max_pdf_pages

    def ingest(
        self,
        *,
        tenant_id: UUID,
        title: str,
        source_name: str,
        source_type: SourceType,
        payload: bytes,
        created_by: UUID | None = None,
    ) -> StoredMetricDocument:
        normalized_title = " ".join(title.split())
        if not normalized_title or len(normalized_title) > 240:
            raise ValueError("title must contain between 1 and 240 characters")
        sections = parse_document(
            source_name=source_name,
            source_type=source_type,
            payload=payload,
            max_markdown_bytes=self._max_markdown_bytes,
            max_pdf_bytes=self._max_pdf_bytes,
            max_pdf_pages=self._max_pdf_pages,
        )
        parsed_chunks = chunk_sections(
            sections,
            max_characters=self._chunk_max_characters,
            overlap_characters=self._chunk_overlap_characters,
        )
        texts = [f"{section.title}\n{section.content}" for section, _ in parsed_chunks]
        vectors = self._embeddings.embed(texts)
        pending = tuple(
            PendingMetricChunk(
                section_key=section.section_key,
                section_title=section.title,
                source_locator=section.source_locator,
                ordinal=ordinal,
                content=section.content,
                embedding=vector,
            )
            for (section, ordinal), vector in zip(parsed_chunks, vectors, strict=True)
        )
        document = self._repository.replace_document(
            tenant_id=tenant_id,
            title=normalized_title,
            source_type=source_type,
            source_name=source_name,
            content_sha256=hashlib.sha256(payload).hexdigest(),
            chunks=pending,
            created_by=created_by,
        )
        self._cache.invalidate_tenant(tenant_id)
        return document

    def retrieve(
        self,
        *,
        tenant_id: UUID,
        query: str,
        mode: RetrievalMode = "hybrid",
        limit: int | None = None,
    ) -> RetrievalResult:
        normalized_query = " ".join(query.split())
        if not normalized_query or len(normalized_query) > 4_000:
            raise ValueError("query must contain between 1 and 4000 characters")
        limit = self._default_limit if limit is None else limit
        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")
        revision = self._repository.corpus_revision(tenant_id)
        cached = self._cache.get(tenant_id, normalized_query, revision, mode, limit)
        if cached is not None:
            return cached

        candidate_limit = min(100, max(limit * 4, 20))
        lexical = (
            self._repository.lexical_search(tenant_id, normalized_query, candidate_limit)
            if mode in ("lexical", "hybrid")
            else ()
        )
        vector = (
            self._repository.vector_search(
                tenant_id, self._embeddings.embed((normalized_query,))[0], candidate_limit
            )
            if mode in ("vector", "hybrid")
            else ()
        )
        hits = self._rank(lexical, vector, mode)[:limit]
        should_answer = self._has_evidence(hits, mode)
        result = RetrievalResult(
            query=normalized_query,
            mode=mode,
            corpus_revision=revision,
            hits=tuple(hits),
            citations=tuple(hit.citation for hit in hits),
            should_answer=should_answer,
        )
        self._cache.put(tenant_id, result, limit)
        return result

    def _rank(
        self,
        lexical: Sequence[RankedChunk],
        vector: Sequence[RankedChunk],
        mode: RetrievalMode,
    ) -> list[RetrievalHit]:
        lexical_by_id = {item.chunk.id: item for item in lexical}
        vector_by_id = {item.chunk.id: item for item in vector}
        if mode == "lexical":
            order = [(item.chunk.id, max(0.0, item.score)) for item in lexical]
        elif mode == "vector":
            order = [(item.chunk.id, max(0.0, item.score)) for item in vector]
        else:
            fused: dict[UUID, float] = {}
            # The local hashing vector is a reproducible baseline, so exact lexical
            # evidence receives the larger production-safe weight in weighted RRF.
            for ranking, weight in ((lexical, 3.0), (vector, 1.0)):
                for rank, item in enumerate(ranking, start=1):
                    fused[item.chunk.id] = fused.get(item.chunk.id, 0.0) + weight / (
                        self._rrf_k + rank
                    )
            order = sorted(fused.items(), key=lambda item: (-item[1], str(item[0])))

        hits = []
        for chunk_id, fused_score in order:
            lexical_item = lexical_by_id.get(chunk_id)
            vector_item = vector_by_id.get(chunk_id)
            item = lexical_item or vector_item
            if item is None:
                continue
            chunk = item.chunk
            hits.append(
                RetrievalHit(
                    content=chunk.content,
                    citation=Citation(
                        document_id=chunk.document_id,
                        document_title=chunk.document_title,
                        document_version=chunk.document_version,
                        section_key=chunk.section_key,
                        section_title=chunk.section_title,
                        source_locator=chunk.source_locator,
                    ),
                    lexical_score=None if lexical_item is None else lexical_item.score,
                    vector_score=None if vector_item is None else vector_item.score,
                    fused_score=fused_score,
                )
            )
        return hits

    def _has_evidence(self, hits: Sequence[RetrievalHit], mode: RetrievalMode) -> bool:
        if not hits:
            return False
        if mode in ("lexical", "hybrid") and any(
            (hit.lexical_score or 0) >= self._min_lexical_score for hit in hits
        ):
            return True
        return mode in ("vector", "hybrid") and any(
            (hit.vector_score or -1) >= self._min_vector_score for hit in hits
        )
