from app.metadata.models import SchemaSnapshot
from app.query_safety.models import QueryPolicy
from app.settings import QuerySafetySettings, get_query_safety_settings


def create_query_policy(
    snapshot: SchemaSnapshot,
    settings: QuerySafetySettings | None = None,
) -> QueryPolicy:
    resolved = settings or get_query_safety_settings()
    return QueryPolicy.from_snapshot(snapshot, **resolved.model_dump())
