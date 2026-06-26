---
title: "SQLite Hybrid Search Requirements"
date: 2026-06-25
topic: sqlite-hybrid-search
---

# SQLite Hybrid Search Requirements

## Summary

Replace the current hash-based, in-memory retrieval projections with a SQLite-native hybrid search layer. The new index uses a durable document projection, SQLite FTS5 for BM25-style exact-term retrieval, sqlite-vec for local vector search, and `BAAI/bge-m3` as the committed local Hugging Face embedding model.

---

## Problem Frame

The Local Core already treats retrieval indexes as rebuildable projections over source-linked Telegram, web, and Manual Knowledge Note chunks. That shape is right, but the current retrieval implementation is a prototype: lexical search is token-overlap scoring in Python, vector search uses hash embeddings, and stored lexical/vector references are JSON side tables rather than queryable search indexes.

The first search-quality gap to close is exact product and policy term recovery. Support workflows need to recover terms such as feature names, account policies, error labels, product-specific nouns, and dated policy language reliably enough that Evidence Bundles do not miss the source record that uses the precise term.

---

## Key Decisions

- **SQLite-native hybrid search is the committed direction.** The retrieval stack should use SQLite FTS5 and sqlite-vec inside the Support Profile instead of introducing a separate vector service.
- **Exact-term recovery is the first success target.** FTS5/BM25 quality matters most in this pass because product and policy terms should not be lost behind fuzzy semantic similarity.
- **`BAAI/bge-m3` is the committed embedding model.** The model should run locally through a Hugging Face-compatible path and its identity should be recorded in index metadata.
- **No backwards-compatible migration is required.** The product has no usage yet, so planning may replace the current lexical/vector projection rather than preserving old index rows.
- **Source records remain authoritative.** Search indexes are still rebuildable projections; Telegram messages, crawled pages, and Manual Knowledge Notes remain the durable evidence sources.

---

## Requirements

**Index Shape**

- R1. The Local Core must keep a durable `documents` projection for retrievable indexed items that preserves source type, source ID, ordinal, text, and metadata needed for Evidence Bundles.
- R2. The Local Core must build an FTS5-backed `fts_documents` projection over indexed document text for BM25-style lexical retrieval.
- R3. The Local Core must build a sqlite-vec-backed `vec_documents` projection over local embeddings for vector retrieval.
- R4. The index build must record the embedding model identity and index version so stale or incompatible projections can be rebuilt.
- R5. The index build may replace the current JSON-based lexical and vector reference projections without preserving compatibility with existing local databases.

**Retrieval Behavior**

- R6. Search must combine FTS lexical results and sqlite-vec vector results into a single ranked Evidence Bundle.
- R7. Search must prioritize recovery of exact product and policy terms when those terms appear in indexed source text.
- R8. Search results must continue to include source references, text, scores, and metadata that let the Agent Surface cite evidence without relying on memory.
- R9. Manual Knowledge Note validity filtering and priority behavior must continue to apply after the retrieval stack changes.
- R10. Conflict checks must continue to compare applicable Manual Knowledge Notes against indexed Telegram and web evidence.

**Local Model and Operations**

- R11. Embeddings must be generated locally with `BAAI/bge-m3`.
- R12. The default setup and index commands must make it clear when local model dependencies are missing or embeddings need to be rebuilt.
- R13. Rebuilding the search index must not delete source records for chats, users, messages, pages, Manual Knowledge Notes, drafts, confirmations, or post attempts.
- R14. The configured embedding model must remain profile-aware so future model changes can trigger a rebuild without changing source records.

---

## Key Flows

- F1. Build a fresh SQLite hybrid index
  - **Trigger:** The operator runs the normal index command after syncing, crawling, or saving Manual Knowledge Notes.
  - **Steps:** The Local Core refreshes indexed documents, updates FTS rows, embeds documents with `BAAI/bge-m3`, writes sqlite-vec rows, and records a successful index run.
  - **Outcome:** Search is ready without changing durable source records.
  - **Covered by:** R1, R2, R3, R4, R11, R13

- F2. Search for an exact product or policy term
  - **Trigger:** The operator or Agent Surface searches for a support question containing a product or policy term.
  - **Steps:** FTS retrieves exact lexical matches, vector search retrieves semantic candidates, and hybrid ranking returns source-linked evidence.
  - **Outcome:** Indexed items using the exact term are recoverable in the Evidence Bundle.
  - **Covered by:** R6, R7, R8

- F3. Search with active manual knowledge
  - **Trigger:** A search query touches a topic covered by an active Manual Knowledge Note.
  - **Steps:** Retrieval filters notes by validity, applies note priority behavior, and runs conflict checks against indexed Telegram and web evidence.
  - **Outcome:** Manual-note influence and conflicts remain visible after the index replacement.
  - **Covered by:** R9, R10

---

## Scope Boundaries

### In Scope

- Replacing the current hash embedding and in-memory scoring path.
- Using SQLite FTS5 for BM25-style exact-term retrieval.
- Using sqlite-vec for local vector retrieval.
- Making `BAAI/bge-m3` the committed embedding model for this project.
- Preserving source-linked Evidence Bundle behavior across Telegram, web, and Manual Knowledge Note sources.

### Deferred for Later

- Evaluating Qdrant, FastEmbed, or hosted vector services.
- Multilingual search-quality tuning beyond what `BAAI/bge-m3` provides by default.
- Learning-to-rank, reranking, query expansion, or synonym dictionaries.
- Search analytics dashboards or relevance-feedback loops.

### Outside This Product's Identity

- Treating index rows as the durable source of support truth.
- Indexing Repository Evidence into stored chunks; repository evidence remains live and branch-aware.
- Maintaining backwards compatibility with pre-product local index projections.

---

## Acceptance Examples

- AE1. **Covers R1, R2, R7.** Given an indexed support source contains an exact product or policy term, when the operator searches for that term, then the FTS path can return the matching document in the Evidence Bundle.
- AE2. **Covers R3, R6, R8.** Given a query uses wording related to an indexed item without matching every term, when search runs, then vector candidates can appear alongside lexical candidates with source metadata.
- AE3. **Covers R9, R10.** Given an active Manual Knowledge Note applies to the query, when search prepares evidence, then note validity, note priority, and conflict reporting still apply.
- AE4. **Covers R11, R12, R14.** Given the configured profile has no usable local embedding dependency or model cache, when indexing needs embeddings, then the command reports the missing local model requirement instead of silently falling back to hash vectors.
- AE5. **Covers R5, R13.** Given an existing prototype database has old lexical/vector projection rows, when the new index is built, then planning may replace those projections while preserving durable source records.

---

## Success Criteria

- Exact product and policy terms present in indexed source text are recoverable through normal search.
- Hybrid search continues to return source-linked Evidence Bundles suitable for support answers and drafts.
- The hash embedding fallback is no longer the normal indexed retrieval path.
- Search index rebuilds are local, deterministic, and safe to repeat against a Support Profile.
- Manual Knowledge Note priority and conflict behavior remain intact after the index replacement.

---

## Dependencies / Assumptions

- The project can add local Python dependencies for Hugging Face-compatible embeddings and sqlite-vec.
- SQLite FTS5 is available in the runtime SQLite build used by supported local environments.
- sqlite-vec packaging works in the expected Python/local CLI environment.
- `BAAI/bge-m3` has acceptable local runtime cost for the first product version.
- The planning phase will choose exact table definitions, adapter boundaries, and dependency packaging.

---

## Sources / Research

- `tg_support/storage/schema.py` currently defines `chunks`, `index_runs`, `lexical_refs`, and `vector_refs` as the retrieval projection tables.
- `tg_support/indexing/embeddings.py` currently provides `HashEmbeddingModel` with `local-hash-v1`.
- `tg_support/indexing/lexical.py` currently scores token overlap in Python.
- `tg_support/indexing/vector.py` currently performs in-memory vector scoring over hash embeddings.
- `tg_support/indexing/hybrid.py` currently fuses lexical and vector results and applies Manual Knowledge Note eligibility and boosting.
- `README.md` describes SQLite as the durable local metadata store and indexes as rebuildable projections.
- `docs/brainstorms/telegram-support-agent-requirements.md` established the original requirement for BM25 or sparse lexical retrieval, dense vector retrieval, and local Hugging Face-compatible embeddings.
- `docs/brainstorms/2026-06-25-github-repo-evidence-requirements.md` keeps Repository Evidence live rather than indexed.
