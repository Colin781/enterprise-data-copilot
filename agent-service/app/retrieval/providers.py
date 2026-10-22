"""Bounded HTTP adapters. Provider response bodies/credentials never enter errors."""

import hashlib
import math
import time
from collections.abc import Sequence

import httpx

from app.retrieval.embeddings import lexical_tokens
from app.retrieval.errors import RetrievalError
from app.retrieval.models import RetrievalHit


class RetrievalProviderError(RetrievalError):
    code = "RETRIEVAL_PROVIDER_FAILED"
    public_message = "Embedding or reranking provider failed; check configuration and reindex."


def post_json(url, payload, *, key, timeout, attempts, client=None) -> dict:
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    # Each retry has a bounded timeout and bounded backoff. Never retry 4xx except 429.
    for attempt in range(attempts):
        try:
            if client is None:
                response = httpx.post(url, json=payload, headers=headers, timeout=timeout)
            else:
                response = client.post(url, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError("invalid provider envelope")
            return result
        except (httpx.HTTPError, ValueError) as error:
            transient = isinstance(error, httpx.TransportError) or (
                isinstance(error, httpx.HTTPStatusError)
                and (error.response.status_code == 429 or error.response.status_code >= 500)
            )
            if not transient or attempt + 1 == attempts:
                raise RetrievalProviderError() from None
            time.sleep(min(0.2 * 2**attempt, 1))
    raise RetrievalProviderError()


class HTTPEmbeddingProvider:
    def __init__(self, *, base_url, model, dimensions, key="", timeout=20, attempts=3, client=None):
        self.dimensions = dimensions
        endpoint = hashlib.sha256(str(base_url).rstrip("/").encode()).hexdigest()[:12]
        self.profile = f"http:{endpoint}:{model}:{dimensions}"
        self.model = model
        self.url = str(base_url).rstrip("/") + "/embeddings"
        self.key, self.timeout, self.attempts, self.client = key, timeout, attempts, client
        self.input_tokens = 0
        self.requests = 0
        self.usage_known = True

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        vectors = []
        for start in range(0, len(texts), 32):
            batch = list(texts[start : start + 32])
            result = post_json(
                self.url,
                {"model": self.model, "input": batch},
                key=self.key,
                timeout=self.timeout,
                attempts=self.attempts,
                client=self.client,
            )
            try:
                data = result["data"]
                if len(data) != len(batch) or {item["index"] for item in data} != set(
                    range(len(batch))
                ):
                    raise ValueError("invalid indexes")
                for item in sorted(data, key=lambda item: item["index"]):
                    vector = tuple(float(value) for value in item["embedding"])
                    if len(vector) != self.dimensions or not all(math.isfinite(v) for v in vector):
                        raise ValueError("invalid dimension or non-finite vector")
                    norm = math.sqrt(sum(v * v for v in vector))
                    if norm == 0:
                        raise ValueError("zero embedding")
                    vectors.append(tuple(v / norm for v in vector))
                usage = result.get("usage", {})
                if "prompt_tokens" not in usage:
                    self.usage_known = False
                self.input_tokens += int(usage.get("prompt_tokens", 0))
                self.requests += 1
            except (KeyError, TypeError, ValueError, OverflowError):
                raise RetrievalProviderError() from None
        return tuple(vectors)


class OverlapReranker:
    """Offline test baseline; this is not a cross-encoder model."""

    name = "overlap-test-baseline"

    def rerank(self, query: str, hits: Sequence[RetrievalHit]) -> list[RetrievalHit]:
        tokens = set(lexical_tokens(query))
        return sorted(hits, key=lambda hit: -len(tokens & set(lexical_tokens(hit.content))))


class HTTPReranker:
    def __init__(self, *, url, model, key="", timeout=20, attempts=3, client=None):
        self.url, self.model, self.key = str(url), model, key
        self.timeout, self.attempts, self.client = timeout, attempts, client
        self.name = f"http:{model}"
        self.requests = 0

    def rerank(self, query: str, hits: Sequence[RetrievalHit]) -> list[RetrievalHit]:
        if not hits:
            return []
        response = post_json(
            self.url,
            {
                "model": self.model,
                "query": query,
                "documents": [hit.content for hit in hits],
                "top_n": len(hits),
            },
            key=self.key,
            timeout=self.timeout,
            attempts=self.attempts,
            client=self.client,
        )
        try:
            self.requests += 1
            results = response["results"]
            if len(results) != len(hits):
                raise ValueError("incomplete ranking")
            indices = [item["index"] for item in results]
            if any(type(i) is not int for i in indices) or set(indices) != set(range(len(hits))):
                raise ValueError("invalid index")
            if any(not math.isfinite(float(item["relevance_score"])) for item in results):
                raise ValueError("invalid score")
            return [
                hits[item["index"]].model_copy(
                    update={
                        "rerank_score": float(item["relevance_score"]),
                    }
                )
                for item in sorted(results, key=lambda item: -float(item["relevance_score"]))
            ]
        except (KeyError, TypeError, ValueError, IndexError):
            raise RetrievalProviderError() from None
