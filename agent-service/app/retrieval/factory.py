from app.retrieval.cache import RetrievalCache
from app.retrieval.embeddings import HashingEmbeddingProvider
from app.retrieval.providers import HTTPEmbeddingProvider, HTTPReranker, OverlapReranker
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
    embeddings = create_embedding_provider(resolved)
    reranker = None
    if resolved.reranker_provider == "overlap":
        reranker = OverlapReranker()
    elif resolved.reranker_provider == "http":
        reranker = HTTPReranker(
            url=resolved.reranker_url,
            model=resolved.reranker_model,
            key=resolved.reranker_api_key.get_secret_value(),
            timeout=resolved.provider_timeout_seconds,
            attempts=resolved.provider_max_attempts,
        )
    return MetricRetrievalService(
        repository=repository,
        embedding_provider=embeddings,
        reranker=reranker,
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


def create_embedding_provider(settings: RetrievalSettings):
    if settings.embedding_provider == "hashing":
        return HashingEmbeddingProvider(settings.embedding_dimensions)
    return HTTPEmbeddingProvider(
        base_url=settings.embedding_base_url,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        key=settings.embedding_api_key.get_secret_value(),
        timeout=settings.provider_timeout_seconds,
        attempts=settings.provider_max_attempts,
    )


def create_production_retrieval_service() -> MetricRetrievalService:
    database = get_platform_database_settings()
    settings = get_retrieval_settings()
    provider = create_embedding_provider(settings)
    profile = getattr(provider, "profile", f"hashing:{settings.embedding_dimensions}")
    repository = PostgresMetricKnowledgeRepository(
        PlatformKnowledgeDatabaseConfig(
            host=database.host,
            port=database.port,
            database=database.name,
            username=database.user,
            password=database.password.get_secret_value(),
        ),
        embedding_profile=profile,
        vector_search_mode=settings.vector_search_mode,
    )
    return create_metric_retrieval_service(repository)
