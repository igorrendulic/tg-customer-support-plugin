from __future__ import annotations

from tg_support.indexing.embeddings import HashEmbeddingModel, cosine
from tg_support.storage.db import ChunkRecord


class InMemoryVectorScorer:
    def __init__(self, model: HashEmbeddingModel | None = None):
        self.model = model or HashEmbeddingModel()

    def search(self, chunks: list[ChunkRecord], query: str, limit: int = 10) -> list[tuple[ChunkRecord, float]]:
        query_vec = self.model.embed(query)
        scored = [(chunk, cosine(query_vec, self.model.embed(chunk.text))) for chunk in chunks]
        return [(chunk, score) for chunk, score in sorted(scored, key=lambda item: (-item[1], item[0].id))[:limit] if score > 0]


InMemoryVectorIndex = InMemoryVectorScorer
