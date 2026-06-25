from __future__ import annotations

import hashlib
import math


class HashEmbeddingModel:
    name = "local-hash-v1"

    def embed(self, text: str, dims: int = 64) -> list[float]:
        vec = [0.0] * dims
        for word in text.lower().split():
            digest = hashlib.sha256(word.encode()).digest()
            idx = int.from_bytes(digest[:2], "big") % dims
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
