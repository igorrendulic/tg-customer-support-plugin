---
title: "feat: Boost username exact matches in support search"
type: feat
date: 2026-06-26
origin: docs/brainstorms/2026-06-26-username-exact-match-boosting-requirements.md
---

# feat: Boost username exact matches in support search

## Summary

Add a metadata-backed exact username match signal to normal support search. Queries such as `crinx7` and `@crinx7` should boost Telegram evidence authored by that username while preserving the existing Evidence Bundle shape.

## Problem Frame

Telegram usernames are stored on source messages and already appear in Telegram chunk text, but search currently treats them as ordinary document text. A username-only query can therefore lose to unrelated lexical or semantic candidates even when the local corpus contains messages authored by that user.

## Requirements

- R1. Search detects exact Telegram username queries with and without a leading `@`.
- R2. Exact matches compare against Telegram author username metadata, not arbitrary raw text mentions.
- R3. Matching Telegram evidence receives a strong boost inside normal retrieval.
- R4. Boosted results remain source-linked Telegram evidence records with existing text and metadata.
- R5. Non-username support queries continue to use existing lexical, vector, Manual Knowledge Note, and Conflict Check behavior.
- R6. Search consumers, including CLI search and draft context, receive the same result shape they currently consume.

## Key Technical Decisions

- KTD1. **Match author metadata, not message text mentions:** The boost should represent messages authored by the queried user, avoiding false positives from someone else mentioning a username in conversation.
- KTD2. **Add the signal inside the retriever:** CLI and Agent Surfaces should keep using normal search and draft-context commands through the Local Core rather than gaining separate user lookup logic.
- KTD3. **Use rank-level boosting over source rewrites:** The existing chunk and document projections can remain source-linked evidence; implementation should add or boost matching candidates rather than rewriting chunks only to influence rank.
- KTD4. **Normalize query and stored usernames consistently:** Case-insensitive matching and optional leading `@` stripping should be centralized so CLI search and draft-context behavior do not diverge.

## Scope Boundaries

- A dedicated participant directory or user-profile search UI is out of scope.
- Boosting raw text mentions of usernames is out of scope for this plan.
- Changing draft targeting behavior is out of scope unless implementation discovers it is required to preserve evidence quality.
- Rebuilding the SQLite Hybrid Search Index schema is out of scope unless implementation discovers current metadata is insufficient.

## Risks & Dependencies

- **Over-boosting unrelated queries:** Short tokens can look username-like. Mitigate by applying boosts only when an exact author username candidate exists.
- **Context-window duplication:** Telegram chunks include neighboring messages, so multiple chunks can contain the same author's name. Mitigate by matching against source message author metadata where possible rather than chunk text alone.
- **Result-shape regression:** Search consumers expect Evidence Bundle dictionaries. Mitigate with CLI or retriever tests that assert boosted results remain normal Telegram evidence.

## Implementation Units

### U1. Username normalization and metadata candidate lookup

- **Goal:** Add a focused path that recognizes username-style queries and finds Telegram documents whose source message author exactly matches the normalized username.
- **Requirements:** R1, R2, R4
- **Dependencies:** None
- **Files:** `tg_support/indexing/hybrid.py`, `tg_support/storage/db.py`, `tests/test_hybrid_retrieval.py`
- **Approach:** Normalize a query by trimming whitespace, stripping one leading `@`, and comparing case-insensitively. Use message author metadata or the `messages.author_username` source table to find matching Telegram evidence, then map those matches back to indexed document records.
- **Execution note:** Start with failing retrieval tests for `crinx7` and `@crinx7` before adding the lookup path.
- **Patterns to follow:** `tg_support/support/context.py` already normalizes `--user` by stripping `@`; `SupportDatabase.documents_by_id` shows the pattern for mapping database IDs back to `DocumentRecord` values.
- **Test scenarios:**
  - Covers origin AE1. Given indexed Telegram evidence authored by `crinx7`, searching `crinx7` returns a Telegram evidence item for that user's message or context.
  - Covers origin AE2. Given the same corpus, searching `@crinx7` behaves like searching `crinx7`.
  - Given indexed Telegram evidence authored by `Crinx7`, searching `crinx7` still finds the author match.
  - Given another user's message text mentions `crinx7`, searching `crinx7` does not treat that text mention as an author exact match.
- **Verification:** Retrieval tests prove exact author username candidates can be found without relying on raw chunk text mentions.

### U2. Hybrid ranking boost integration

- **Goal:** Merge exact username candidates into normal hybrid retrieval so they outrank weaker lexical and vector matches while preserving non-username behavior.
- **Requirements:** R3, R4, R5
- **Dependencies:** U1
- **Files:** `tg_support/indexing/hybrid.py`, `tg_support/indexing/lexical.py`, `tests/test_hybrid_retrieval.py`
- **Approach:** Add username candidates as a separate retrieval signal or post-fusion boost before final sorting. Keep Manual Knowledge Note validity filtering and conflict logic after candidate fusion so existing support-truth behavior remains intact.
- **Patterns to follow:** `reciprocal_rank_fusion` already treats retrieval channels as rank signals, and `HybridRetriever.search` already applies manual-note boosting before the final result cut.
- **Test scenarios:**
  - Covers origin AE1. Given a username match and weaker lexical or vector candidates, the username-authored Telegram evidence appears near the top of results.
  - Covers origin AE3. Given no exact author username match, topic searches continue to return existing lexical and semantic evidence.
  - Given an active Manual Knowledge Note for a policy query, manual-note priority remains unchanged when no username author match exists.
  - Given a username match, the returned result includes `chunk_id`, `document_id`, `source_type`, `source_id`, `text`, and `metadata`.
- **Verification:** Hybrid retrieval tests show username exact matches affect ranking only when author metadata matches and do not regress exact policy-term or manual-note scenarios.

### U3. CLI and draft-context consumer coverage

- **Goal:** Prove the boosted retrieval behavior is visible through normal operator commands and remains compatible with downstream Evidence Bundle consumers.
- **Requirements:** R4, R5, R6
- **Dependencies:** U2
- **Files:** `tg_support/cli.py`, `tg_support/support/context.py`, `tests/test_cli_setup.py`, `tests/test_manual_knowledge.py`, `skills/telegram-support/references/analytics-workflow.md`
- **Approach:** Keep command behavior unchanged unless tests expose a compatibility gap. Add consumer-level coverage around `search` and draft-context paths so the boost remains a Local Core behavior shared by thin Agent Surfaces.
- **Patterns to follow:** `tests/test_cli_setup.py::test_draft_context_for_known_user` verifies draft-context shape, and `docs/solutions/architecture-patterns/thin-agent-surfaces-shared-local-cli-core.md` requires retrieval behavior to stay in the shared CLI/core.
- **Test scenarios:**
  - Covers origin AE4. CLI search for a username returns normal evidence JSON, not a separate user record.
  - Draft context using a query derived from user history can consume a boosted username result without special casing.
  - Existing missing-index and retrieval dependency error paths still return their current JSON payloads.
  - Agent-facing workflow docs do not instruct operators to use a separate user search command for this behavior.
- **Verification:** CLI and support-context tests prove normal consumers see the boosted result through the existing command boundary.

## Documentation / Operational Notes

No operator-facing command change is planned. If implementation changes observable search behavior enough to mention, update the analytics workflow to say exact Telegram author usernames are recoverable through normal `search`.

## Sources / Research

- `docs/brainstorms/2026-06-26-username-exact-match-boosting-requirements.md` defines the origin requirements and scope boundaries.
- `tg_support/storage/schema.py` stores `messages.author_username` and indexes it with `sent_at`.
- `tg_support/indexing/chunking.py` already includes usernames in Telegram chunk text, so the missing behavior is ranking strength rather than username inclusion.
- `tg_support/indexing/hybrid.py` owns retrieval fusion, manual-note boosting, and result shaping.
- `tg_support/support/context.py` contains the existing direct user-history normalization pattern for `--user`.
- `docs/solutions/architecture-patterns/thin-agent-surfaces-shared-local-cli-core.md` reinforces keeping retrieval behavior inside the shared Local Core.
