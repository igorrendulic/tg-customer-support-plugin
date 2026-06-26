---
date: 2026-06-26
topic: username-exact-match-boosting
---

# Username Exact Match Boosting Requirements

## Summary

Normal support search should strongly boost exact Telegram username matches. When a message was authored by a username such as `crinx7`, searching that username should reliably surface source-linked Telegram evidence ahead of weaker semantic matches.

---

## Problem Frame

Support operators use search to recover the local evidence needed for analytics and reply drafting. Telegram usernames are already stored with messages and included in Telegram chunk text, but normal search ranks evidence chunks rather than treating author metadata as a first-class exact-match signal. This can make a visible username mention in Telegram hard to recover through ordinary search.

---

## Key Decisions

- **Boost exact username matches inside existing evidence search.** The operator should not need a separate user lookup flow when they are searching for answerable support context.
- **Return evidence, not bare user records.** A username match should surface the relevant Telegram message or context chunk with metadata so downstream support workflows can cite and use it.
- **Keep semantic retrieval secondary for username-only queries.** Vector or semantic matches may still appear, but exact author username matches should outrank weaker candidates.

---

## Requirements

- R1. Search must detect exact Telegram username queries with or without a leading `@`.
- R2. When a Telegram message author username exactly matches the query, normal search must strongly boost the matching Telegram evidence.
- R3. Boosted username matches must return source-linked Telegram evidence, including the message or context text and existing metadata.
- R4. Username exact-match boosting must not remove or weaken normal evidence retrieval for non-username queries.
- R5. Username matching must be case-insensitive.
- R6. Search results must remain compatible with evidence bundle consumers, including analytics and draft context.

---

## Acceptance Examples

- AE1. **Covers R1, R2, R3, R5.** Given indexed Telegram evidence authored by `crinx7`, when the operator searches `crinx7`, then the returned evidence includes that user's Telegram message or context chunk near the top of results.
- AE2. **Covers R1, R2, R3, R5.** Given indexed Telegram evidence authored by `crinx7`, when the operator searches `@crinx7`, then the search behaves like the bare username query.
- AE3. **Covers R2, R4.** Given no exact author username matches the query, when the operator searches a support topic, then existing lexical and semantic evidence retrieval still determines the result set.
- AE4. **Covers R3, R6.** Given a username match is boosted, when the result is consumed by analytics or draft context, then it remains a normal source-linked Telegram evidence item rather than a separate user record.

---

## Scope Boundaries

- A dedicated participant directory or user-profile search UI is out of scope.
- Returning a bare "user found" record as support evidence is out of scope.
- Changing draft targeting behavior is out of scope unless planning finds it necessary to preserve evidence quality.

---

## Success Criteria

- Exact author username searches recover relevant Telegram evidence consistently.
- Username-only searches no longer miss visible Telegram participants because their names are treated only as ordinary chunk text.
- Existing evidence bundle shape remains stable for downstream support workflows.

---

## Sources / Research

- `tg_support/storage/schema.py` stores Telegram message authors in `messages.author_username` and indexes that field with message timestamps.
- `tg_support/indexing/chunking.py` includes author usernames in Telegram chunk text.
- `tg_support/indexing/hybrid.py` fuses lexical and vector retrieval into normal evidence search results.
- `tg_support/support/context.py` has a separate direct user-history path for draft context, but the chosen scope targets normal search ranking.
