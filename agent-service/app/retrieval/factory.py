from app.retrieval.cache import RetrievalCache
from app.retrieval.embeddings import HashingEmbeddingProvider
from app.retrieval.repository import (
    MetricKnowledgeRepository,
    PlatformKnowledgeDatabaseConfig,
    PostgresMetricKnowledgeRepository,
)
from app.retrieval.service import MetricRetrievalService
from app.settings import (
    RetrievalSettings,
    get_platform_database_settings,
    get_retrieval_settings,
)


def create_metric_retrieval_service(
    repository: MetricKnowledgeRepository,
    settings: RetrievalSettings | None = None,
) -> MetricRetrievalService:
    resolved = settings or get_retrieval_settings()
    return MetricRetrievalService(
        repository=repository,
        embedding_provider=HashingEmbeddingProvider(resolved.embedding_dimensions),
        cache=RetrievalCache(resolved.cache_ttl_seconds),
        chunk_max_characters=resolved.chunk_max_characters,
        chunk_overlap_characters=resolved.chunk_overlap_characters,
        default_limit=resolved.result_limit,
        rrf_k=resolved.rrf_k,
        min_lexical_score=resolved.min_lexical_score,
        min_vector_score=resolved.min_vector_score,
        max_markdown_bytes=resolved.max_markdown_bytes,
        max_pdf_bytes=resolved.max_pdf_bytes,
        max_pdf_pages=resolved.max_pdf_pages,
    )


def create_production_retrieval_service() -> MetricRetrievalService:
    database = get_platform_database_settings()
    repository = PostgresMetricKnowledgeRepository(
        PlatformKnowledgeDatabaseConfig(
            host=database.host,
            port=database.port,
            database=database.name,
            username=database.user,
            password=database.password.get_secret_value(),
        )
    )
    return create_metric_retrieval_service(repository)
