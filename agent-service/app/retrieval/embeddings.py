import hashlib
import math
import re
from collections import Counter
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

_LATIN_OR_NUMBER = re.compile(r"[a-z0-9]+")
_CHINESE_RUN = re.compile(r"[\u4e00-\u9fff]+")


@runtime_checkable
class EmbeddingProvider(Protocol):
    @property
    def dimensions(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]: ...


class HashingEmbeddingProvider:
    """Deterministic, zero-network baseline; replaceable by a model-backed provider."""

    def __init__(self, dimensions: int = 64) -> None:
        if not 16 <= dimensions <= 2_048:
            raise ValueError("dimensions must be between 16 and 2048")
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        return tuple(self._embed_one(text) for text in texts)

    def _embed_one(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self._dimensions
        counts = Counter(vector_tokens(text))
        for token, count in counts.items():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:8], "big") % self._dimensions
            sign = 1.0 if digest[8] & 1 else -1.0
            vector[index] += sign * (1.0 + math.log(count))
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return tuple(vector)


def lexical_tokens(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    tokens = list(_LATIN_OR_NUMBER.findall(lowered))
    for run in _CHINESE_RUN.findall(lowered):
        tokens.extend(run[index : index + 2] for index in range(max(1, len(run) - 1)))
    return tuple(tokens)


def vector_tokens(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    tokens = list(_LATIN_OR_NUMBER.findall(lowered))
    for run in _CHINESE_RUN.findall(lowered):
        for size in (1, 2, 3):
            tokens.extend(run[index : index + size] for index in range(max(1, len(run) - size + 1)))
    return tuple(tokens)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions do not match")
    return sum(first * second for first, second in zip(left, right, strict=True))
