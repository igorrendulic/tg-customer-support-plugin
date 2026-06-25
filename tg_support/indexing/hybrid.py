from __future__ import annotations

from tg_support.indexing.lexical import lexical_search, tokenize
from tg_support.indexing.vector import InMemoryVectorScorer
from tg_support.storage.db import ChunkRecord, SupportDatabase


def reciprocal_rank_fusion(result_sets: list[list[tuple[ChunkRecord, float]]], limit: int = 10, k: int = 60) -> list[tuple[ChunkRecord, float]]:
    scores: dict[int, float] = {}
    chunks: dict[int, ChunkRecord] = {}
    for results in result_sets:
        for rank, (chunk, _score) in enumerate(results, start=1):
            chunks[chunk.id] = chunk
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (k + rank)
    return [(chunks[id_], score) for id_, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]]


class HybridRetriever:
    def __init__(self, db: SupportDatabase, vector_index: InMemoryVectorScorer | None = None):
        self.db = db
        self.vector_index = vector_index or InMemoryVectorScorer()

    def build(self, embedding_model: str = "local-hash-v1") -> int:
        chunks = self.db.chunks()
        self.db.save_index_entries(
            ((chunk.id, tokenize(chunk.text)) for chunk in chunks),
            ((chunk.id, embedding_model, self.vector_index.model.embed(chunk.text)) for chunk in chunks),
        )
        return self.db.record_index_run(embedding_model, "hybrid-v1")

    def stale(self, embedding_model: str = "local-hash-v1") -> bool:
        latest = self.db.latest_index_run(embedding_model)
        if latest is None or latest["status"] != "ok":
            return True
        return self.db.max_chunk_id() > latest["source_max_chunk_id"]

    def search(self, query: str, limit: int = 8) -> list[dict]:
        chunks = self.db.chunks()
        fused = reciprocal_rank_fusion(
            [lexical_search(chunks, query, limit=limit), self.vector_index.search(chunks, query, limit=limit)],
            limit=limit,
        )
        return [
            {
                "chunk_id": chunk.id,
                "source_type": chunk.source_type,
                "source_id": chunk.source_id,
                "score": score,
                "text": chunk.text,
                "metadata": chunk.metadata,
            }
            for chunk, score in fused
        ]
