from __future__ import annotations

from datetime import date, datetime
import re

from tg_support.indexing.embeddings import EmbeddingModel, RetrievalDependencyError
from tg_support.indexing.lexical import lexical_search
from tg_support.indexing.vector import VectorSearcher, VectorStore
from tg_support.storage.db import DocumentRecord, SupportDatabase

AUTHOR_IDENTITY_RE = re.compile(r"@?[a-z0-9_][a-z0-9_ -]*", re.I)
USERNAME_MATCH_BOOST = 20.0
FUZZY_AUTHOR_MATCH_BOOST = 6.0
OPERATOR_EXCHANGE_BOOST = 8.0


def reciprocal_rank_fusion(result_sets: list[list[tuple[DocumentRecord, float]]], limit: int = 10, k: int = 60) -> list[tuple[DocumentRecord, float]]:
    scores: dict[int, float] = {}
    documents: dict[int, DocumentRecord] = {}
    for results in result_sets:
        for rank, (document, _score) in enumerate(results, start=1):
            documents[document.id] = document
            scores[document.id] = scores.get(document.id, 0.0) + 1.0 / (k + rank)
    return [(documents[id_], score) for id_, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]]


class HybridRetriever:
    index_version = "sqlite-hybrid-v1"

    def __init__(
        self,
        db: SupportDatabase,
        embedding_model: EmbeddingModel | None = None,
        vector_store: VectorStore | None = None,
    ):
        self.db = db
        self.vector_searcher = VectorSearcher(db, model=embedding_model, store=vector_store)

    def build(self, embedding_model: str | None = None) -> int:
        model_name = embedding_model or self.vector_searcher.model.name
        documents = self.db.rebuild_documents()
        self.vector_searcher.rebuild(documents)
        return self.db.record_index_run(model_name, self.index_version)

    def stale(self, embedding_model: str | None = None) -> bool:
        model_name = embedding_model or self.vector_searcher.model.name
        latest = self.db.latest_index_run(model_name)
        if latest is None or latest["status"] != "ok" or latest["index_version"] != self.index_version:
            return True
        return self.db.max_chunk_id() > latest["source_max_chunk_id"] or self.db.chunk_signature() != latest["source_signature"]

    def search(
        self,
        query: str,
        limit: int = 8,
        as_of: date | None = None,
        include_inactive_manual: bool = False,
        username: str | None = None,
    ) -> list[dict]:
        author_identity = self._normalized_author_identity(username)
        if not query.strip() and author_identity is None:
            return []
        as_of = as_of or date.today()
        documents = [document for document in self.db.documents() if include_inactive_manual or self._eligible(document, as_of)]
        candidate_limit = max(limit * 4, 20)
        username_matches = self._username_author_matches(author_identity) if author_identity is not None else []
        username_match_ids = {document.id for document in username_matches}
        fuzzy_author_matches = [] if username_matches or author_identity is None else self._fuzzy_author_matches(author_identity)
        fuzzy_author_match_ids = {document.id for document in fuzzy_author_matches}
        author_side_channel = [*username_matches, *fuzzy_author_matches]
        fused = self._fused_search(documents, query, candidate_limit, author_side_channel)
        boosted = [
            (
                document,
                score
                + (10.0 if document.source_type == "manual" and self._eligible(document, as_of) else 0.0)
                + (USERNAME_MATCH_BOOST if document.id in username_match_ids else 0.0)
                + (FUZZY_AUTHOR_MATCH_BOOST if document.id in fuzzy_author_match_ids else 0.0)
                + self._exchange_authority_boost(document),
            )
            for document, score in fused
        ]
        return [self._result_dict(document, score) for document, score in sorted(boosted, key=lambda item: (-item[1], item[0].id))[:limit]]

    def search_with_conflicts(self, query: str, limit: int = 8, as_of: date | None = None, username: str | None = None) -> dict:
        as_of = as_of or date.today()
        evidence = self.search(query, limit=limit, as_of=as_of, username=username)
        conflicts = self._conflicts_for(query, evidence, limit=limit, as_of=as_of)
        return {"evidence": evidence, "conflicts": conflicts}

    def _fused_search(
        self,
        documents: list[DocumentRecord],
        query: str,
        limit: int,
        author_side_channel: list[DocumentRecord] | None = None,
    ) -> list[tuple[DocumentRecord, float]]:
        if not documents:
            return []
        eligible_ids = {document.id for document in documents}
        lexical = []
        vector = []
        if query.strip():
            lexical = [(document, score) for document, score in lexical_search(self.db, query, limit=limit) if document.id in eligible_ids]
            vector = [(document, score) for document, score in self.vector_searcher.search(query, limit=limit) if document.id in eligible_ids]
        author = [(document, 1.0) for document in author_side_channel or [] if document.id in eligible_ids]
        return reciprocal_rank_fusion([author, lexical, vector], limit=limit)

    def _username_author_matches(self, author_identity: str) -> list[DocumentRecord]:
        return self.db.telegram_documents_by_author_username(author_identity)

    def _fuzzy_author_matches(self, author_identity: str) -> list[DocumentRecord]:
        return self.db.telegram_documents_by_fuzzy_author_identity(author_identity)

    def _normalized_author_identity(self, username: str | None) -> str | None:
        if username is None:
            return None
        candidate = username.strip()
        if not AUTHOR_IDENTITY_RE.fullmatch(candidate):
            return None
        return candidate.removeprefix("@").casefold()

    def _conflicts_for(self, query: str, evidence: list[dict], limit: int, as_of: date) -> list[dict]:
        manual_results = [result for result in evidence if result["source_type"] == "manual"]
        if not manual_results:
            return []
        non_manual_documents = [document for document in self.db.documents() if document.source_type != "manual"]
        non_manual = [
            self._result_dict(document, score)
            for document, score in self._fused_search(non_manual_documents, query, limit=max(limit * 2, 4))
        ]
        conflicts = []
        for note in manual_results:
            effective_raw = note["metadata"].get("effective_date")
            effective = date.fromisoformat(effective_raw) if effective_raw else as_of
            older = [item for item in non_manual if (self._source_date(item) or date.min) < effective]
            if not older:
                continue
            fresher = [item for item in non_manual if (self._source_date(item) or date.min) >= effective]
            conflicts.append(
                {
                    "manual_note": note,
                    "older_evidence": older[:limit],
                    "fresher_evidence": fresher[:limit],
                    "resolution_required": True,
                }
            )
        return conflicts

    def _result_dict(self, document: DocumentRecord, score: float) -> dict:
        return {
            "chunk_id": document.chunk_id,
            "document_id": document.id,
            "source_type": document.source_type,
            "source_id": document.source_id,
            "score": score,
            "text": document.text,
            "metadata": document.metadata,
            "source_updated_at": document.source_updated_at,
        }

    def _source_date(self, result: dict) -> date | None:
        raw = result.get("source_updated_at") or result["metadata"].get("sent_at") or result["metadata"].get("fetched_at")
        if not raw:
            return None
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()

    def _eligible(self, document: DocumentRecord, as_of: date) -> bool:
        if document.source_type != "manual":
            return True
        effective = document.metadata.get("effective_date")
        if effective and date.fromisoformat(effective) > as_of:
            return False
        expires = document.metadata.get("expires_date")
        if expires and date.fromisoformat(expires) < as_of:
            return False
        return True

    def _exchange_authority_boost(self, document: DocumentRecord) -> float:
        if document.source_type != "exchange":
            return 0.0
        if document.metadata.get("status") == "answered_by_operator":
            return OPERATOR_EXCHANGE_BOOST
        return 0.0


__all__ = ["HybridRetriever", "RetrievalDependencyError", "reciprocal_rank_fusion"]
