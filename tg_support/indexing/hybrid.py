from __future__ import annotations

from datetime import date, datetime

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

    def search(self, query: str, limit: int = 8, as_of: date | None = None, include_inactive_manual: bool = False) -> list[dict]:
        as_of = as_of or date.today()
        chunks = [chunk for chunk in self.db.chunks() if include_inactive_manual or self._eligible(chunk, as_of)]
        candidate_limit = max(limit * 4, 20)
        fused = self._fused_search(chunks, query, candidate_limit)
        boosted = [
            (chunk, score + 10.0 if chunk.source_type == "manual" and self._eligible(chunk, as_of) else score)
            for chunk, score in fused
        ]
        return [
            {
                "chunk_id": chunk.id,
                "source_type": chunk.source_type,
                "source_id": chunk.source_id,
                "score": score,
                "text": chunk.text,
                "metadata": chunk.metadata,
            }
            for chunk, score in sorted(boosted, key=lambda item: (-item[1], item[0].id))[:limit]
        ]

    def search_with_conflicts(self, query: str, limit: int = 8, as_of: date | None = None) -> dict:
        as_of = as_of or date.today()
        evidence = self.search(query, limit=limit, as_of=as_of)
        conflicts = self._conflicts_for(query, evidence, limit=limit, as_of=as_of)
        return {"evidence": evidence, "conflicts": conflicts}

    def _fused_search(self, chunks: list[ChunkRecord], query: str, limit: int) -> list[tuple[ChunkRecord, float]]:
        return reciprocal_rank_fusion(
            [lexical_search(chunks, query, limit=limit), self.vector_index.search(chunks, query, limit=limit)],
            limit=limit,
        )

    def _conflicts_for(self, query: str, evidence: list[dict], limit: int, as_of: date) -> list[dict]:
        manual_results = [result for result in evidence if result["source_type"] == "manual"]
        if not manual_results:
            return []
        non_manual_chunks = [chunk for chunk in self.db.chunks() if chunk.source_type != "manual"]
        non_manual = [
            self._result_dict(chunk, score)
            for chunk, score in self._fused_search(non_manual_chunks, query, limit=max(limit * 2, 4))
        ]
        conflicts = []
        for note in manual_results:
            effective_raw = note["metadata"].get("effective_date")
            effective = date.fromisoformat(effective_raw) if effective_raw else as_of
            older = [item for item in non_manual if (self._source_date(item["metadata"]) or date.min) < effective]
            if not older:
                continue
            fresher = [item for item in non_manual if (self._source_date(item["metadata"]) or date.min) >= effective]
            conflicts.append(
                {
                    "manual_note": note,
                    "older_evidence": older[:limit],
                    "fresher_evidence": fresher[:limit],
                    "resolution_required": True,
                }
            )
        return conflicts

    def _result_dict(self, chunk: ChunkRecord, score: float) -> dict:
        return {
            "chunk_id": chunk.id,
            "source_type": chunk.source_type,
            "source_id": chunk.source_id,
            "score": score,
            "text": chunk.text,
            "metadata": chunk.metadata,
        }

    def _source_date(self, metadata: dict) -> date | None:
        raw = metadata.get("sent_at") or metadata.get("fetched_at")
        if not raw:
            return None
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()

    def _eligible(self, chunk: ChunkRecord, as_of: date) -> bool:
        if chunk.source_type != "manual":
            return True
        effective = chunk.metadata.get("effective_date")
        if effective and date.fromisoformat(effective) > as_of:
            return False
        expires = chunk.metadata.get("expires_date")
        if expires and date.fromisoformat(expires) < as_of:
            return False
        return True
