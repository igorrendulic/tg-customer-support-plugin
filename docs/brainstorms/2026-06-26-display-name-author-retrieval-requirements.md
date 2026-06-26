---
title: "Display Name Author Retrieval Requirements"
date: 2026-06-26
topic: display-name-author-retrieval
---

# Display Name Author Retrieval Requirements

## Summary

Support search and draft context must recover clean Telegram evidence by searching all visible Telegram author identity fields: handle/username and display name. Exact author lookup should match either field, while fuzzy identity matching should help discovery without silently treating an ambiguous fuzzy hit as the target user for drafting.

Indexed Telegram evidence must also make those visible author identities available to embedding-based retrieval. If a Telegram author has both a username and a display name, both identity strings should be included in the text that is embedded, while the displayed evidence can keep using the best local author label.

---

## Problem Frame

Author lookup has been too narrow. The first version only matched `messages.author_username`; the later display-name fallback still only used display name when `author_username` was absent. That misses cases where the operator searches a visible display name such as `Anon`, but the stored Telegram author also has a separate handle.

This makes the Agent Surface report `missing_user_history` even though the user and the relevant support exchange are present in the local database.

Telegram chunks also include noisy blank author lines such as `yonghengyige:` and `unknown:` when neighboring messages have empty text or missing usernames. Non-English messages, including Chinese support requests, can be retrieved by exact phrase or vector search, but English-only support drafting benefits from translated context. Translation should enrich retrieval and drafting, not replace the original Telegram evidence or cause the Agent Surface to answer users in the wrong language.

---

## Key Decisions

- **Visible author identity should be searchable.** Handles and display names should both participate in exact author lookup.
- **Visible author identity should be embedding-visible.** Handles and display names should both be included in the indexed text used for embeddings, not only in metadata.
- **Fuzzy identity search is discovery, not automatic target resolution.** Fuzzy username or display-name matches may help find likely users, but draft context must not cite a fuzzy match as the target without an exact match or disambiguation.
- **Chunks should preserve the best local author label.** Telegram chunks should not render `unknown:` when a linked user display name exists.
- **Original Telegram text remains source truth.** Any English translation is derived helper context and must not replace or overwrite the original message.
- **Chunk text should reduce indexing noise.** Empty Telegram messages and blank author labels should not create standalone indexed lines.
- **Replies should match the user's language.** Translation may help the operator understand evidence, but draft replies should default to the Support User's original language when that language can be inferred.

---

## Requirements

**Author Identity Resolution**

- R1. Message chunking must use the best available author label: `author_username` first, then linked `users.display_name`, then `unknown`.
- R2. Telegram chunk metadata must preserve the same best available author label used in chunk text.
- R3. User history lookup must match a requested user string exactly against both `author_username` and linked `users.display_name`.
- R4. Author exact-match boosting must use an explicit requested author identity, separate from free-text query text.

**Telegram Chunk Formatting**

- R5. Message chunking must skip empty or whitespace-only Telegram messages when rendering searchable chunk text.
- R6. Chunk text must avoid standalone `unknown:` or `<author>:` lines that contain no message content.
- R7. Chunk metadata must keep enough original message identifiers and timestamps for evidence display to trace back to the Telegram source.
- R8. The text embedded for Telegram evidence must include every visible author identity available for the source message: username when present, display name when present, or both when both exist.
- R9. Embedding-visible author identity text must not force evidence display to show duplicate labels or replace the best local author label.

**Multilingual Retrieval**

- R10. Telegram ingestion or indexing may generate English translations for non-English messages as derived helper context.
- R11. Derived translations must be stored separately from original Telegram text and must identify the source language when known.
- R12. Search should be able to match both original text and derived English translation when translation is available.
- R13. Evidence output must preserve the original Telegram text and may include translated text as helper context for drafting.

**Multilingual Drafting**

- R14. Draft context must expose the inferred source language for the target message or user history when it is known.
- R15. Reply drafting should default to the Support User's original language when the user wrote in a non-English language.
- R16. English helper translations may guide understanding, but they must not force the final reply language to English.
- R17. If the target language is uncertain, the Agent Surface should make the language assumption visible to the Support Operator before posting.

**Search Behavior**

- R18. Searching with requested author identity `crinx7` or `@crinx7` must recover the source-linked Telegram evidence for a stored display-name author `crinx7`.
- R19. Display-name author matching must be case-insensitive.
- R20. Display-name matching must not treat arbitrary message text mentions as author matches.
- R21. Search may return fuzzy author identity matches across username and display name only when exact author matching returns no author evidence.
- R22. Draft context must require an exact author identity match or explicit disambiguation before using fuzzy-matched user history as the target history.
- R23. Fuzzy author identity search must use index-visible username and display-name terms rather than assuming rendered chunk text contains every identity field.

---

## Acceptance Examples

- AE1. **Covers R1, R2.** Given a message has `author_username = null` and linked `users.display_name = crinx7`, when messages are chunked, then the chunk text starts with `crinx7:` and metadata author is `crinx7`.
- AE2. **Covers R3.** Given an author has `author_username = helper123` and linked `users.display_name = Anon`, when `draft-context --user Anon` runs, then exact target history includes that author's messages.
- AE3. **Covers R8, R9.** Given an author has `author_username = helper123` and linked `users.display_name = Anon`, when Telegram evidence is embedded, then both `helper123` and `Anon` are present in the embedded text without duplicating the visible author label in returned evidence.
- AE4. **Covers R4, R18, R19.** Given indexed Telegram evidence authored by display-name `crinx7`, when the operator searches with requested author identity `crinx7` or `@crinx7`, then that evidence is boosted ahead of unrelated semantic results even if the author also has a separate username.
- AE5. **Covers R20.** Given another user's message text mentions `crinx7`, when the author is not `crinx7`, then that text mention is not treated as an author exact match.
- AE6. **Covers R5, R6.** Given a Telegram window contains empty messages, when chunks are built, then those empty messages do not appear as blank `author:` or `unknown:` lines in searchable text.
- AE7. **Covers R10, R11, R12, R13.** Given a Chinese Telegram message is ingested and translated, when the operator searches an English equivalent, then search can return the original Telegram evidence with translated helper context.
- AE8. **Covers R14, R15, R16.** Given the target support user wrote in Chinese, when the Agent Surface drafts a reply, then the proposed reply is in Chinese while evidence may include English helper translation for the operator.
- AE9. **Covers R17.** Given the target language cannot be inferred confidently, when the Agent Surface drafts a reply, then it shows the language assumption before the Support Operator confirms posting.
- AE10. **Covers R21, R22, R23.** Given no exact author identity matches `Ann`, when fuzzy search finds indexed identity term `Anon`, then search may show the candidate but `draft-context --user Ann` does not use `Anon` as target history without disambiguation.

---

## Scope Boundaries

- This does not allow fuzzy author matches to silently become draft targets.
- This does not create a separate user-profile lookup UI.
- This does not change Manual Knowledge truth or conflict semantics.
- This does not change vector scoring semantics beyond ensuring Telegram author identities are present in embedded text.
- This does not replace original Telegram text with translated text.
- This does not require automatic translation before display-name author retrieval can ship.

---

## Success Criteria

- Visible Telegram display-name authors are not lost as `unknown` in chunks.
- Telegram embeddings include all visible author identities when both username and display name exist.
- Empty Telegram messages do not create noisy searchable author-only lines.
- Search retrieves the local support exchange when `crinx7` is passed as the requested author identity, with or without a separate Telegram handle.
- `draft-context --user Anon` no longer reports missing user history when `Anon` exactly matches the target display name.
- Fuzzy username and display-name search helps operators find likely users only after exact author lookup misses, without bypassing draft-context target safety.
- Non-English Telegram support requests can be searched through original text and, when available, English helper translation.
- Draft replies preserve the Support User's original language when that language can be inferred.

---

## Sources / Research

- `tg_support/telegram_client.py` stores sender username in `author_username` and sender first name/title in `author_name`.
- `tg_support/storage/db.py` stores `author_name` as `users.display_name` and exposes `author_identities` across username and display name.
- `tg_support/indexing/chunking.py` renders the best available `author_label` in Telegram chunk text and stores all visible identities in chunk metadata.
- `tg_support/storage/db.py` adds `author_identities` to FTS text, but `tg_support/indexing/vector.py` embeds `DocumentRecord.text`, which currently comes from chunk text.
