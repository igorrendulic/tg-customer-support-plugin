---
title: "Display Name Author Retrieval Requirements"
date: 2026-06-26
topic: display-name-author-retrieval
---

# Display Name Author Retrieval Requirements

## Summary

Support search and draft context must recover clean Telegram evidence for users who have no Telegram username but do have a display name. A visible author label such as `crinx7` should remain searchable and usable for author matching when Telegram stores it as a display name rather than `author_username`, and multilingual messages should remain understandable without losing the original source text or the user's reply language.

---

## Problem Frame

The username exact-match boost only matches `messages.author_username`. That misses users whose Telegram sender has no username but whose display name is visible in the support chat. In the local profile, `crinx7` exists in `users.display_name`, while the matching message row has an empty `messages.author_username`, so chunks render the author as `unknown:` and `search crinx7` returns unrelated low-score results.

This makes the Agent Surface report `missing_user_history` even though the user and the relevant support exchange are present in the local database.

Telegram chunks also include noisy blank author lines such as `yonghengyige:` and `unknown:` when neighboring messages have empty text or missing usernames. Non-English messages, including Chinese support requests, can be retrieved by exact phrase or vector search, but English-only support drafting benefits from translated context. Translation should enrich retrieval and drafting, not replace the original Telegram evidence or cause the Agent Surface to answer users in the wrong language.

---

## Key Decisions

- **Visible author identity should be searchable.** Display names should participate in author lookup when usernames are absent.
- **Username semantics stay exact.** Exact username matching should not become broad fuzzy people search.
- **Chunks should preserve the best local author label.** Telegram chunks should not render `unknown:` when a linked user display name exists.
- **Original Telegram text remains source truth.** Any English translation is derived helper context and must not replace or overwrite the original message.
- **Chunk text should reduce indexing noise.** Empty Telegram messages and blank author labels should not create standalone indexed lines.
- **Replies should match the user's language.** Translation may help the operator understand evidence, but draft replies should default to the Support User's original language when that language can be inferred.

---

## Requirements

**Author Identity Resolution**

- R1. Message chunking must use the best available author label: `author_username` first, then linked `users.display_name`, then `unknown`.
- R2. Telegram chunk metadata must preserve the same best available author label used in chunk text.
- R3. User history lookup must match a requested handle against `author_username` and, when username is absent, linked `users.display_name`.
- R4. Author exact-match boosting must include Telegram documents whose linked user display name exactly matches the query when `author_username` is absent.

**Telegram Chunk Formatting**

- R5. Message chunking must skip empty or whitespace-only Telegram messages when rendering searchable chunk text.
- R6. Chunk text must avoid standalone `unknown:` or `<author>:` lines that contain no message content.
- R7. Chunk metadata must keep enough original message identifiers and timestamps for evidence display to trace back to the Telegram source.

**Multilingual Retrieval**

- R8. Telegram ingestion or indexing may generate English translations for non-English messages as derived helper context.
- R9. Derived translations must be stored separately from original Telegram text and must identify the source language when known.
- R10. Search should be able to match both original text and derived English translation when translation is available.
- R11. Evidence output must preserve the original Telegram text and may include translated text as helper context for drafting.

**Multilingual Drafting**

- R12. Draft context must expose the inferred source language for the target message or user history when it is known.
- R13. Reply drafting should default to the Support User's original language when the user wrote in a non-English language.
- R14. English helper translations may guide understanding, but they must not force the final reply language to English.
- R15. If the target language is uncertain, the Agent Surface should make the language assumption visible to the Support Operator before posting.

**Search Behavior**

- R16. Searching `crinx7` or `@crinx7` must recover the source-linked Telegram evidence for a stored display-name author `crinx7`.
- R17. Display-name author matching must be case-insensitive.
- R18. Display-name matching must not treat arbitrary message text mentions as author matches.

---

## Acceptance Examples

- AE1. **Covers R1, R2.** Given a message has `author_username = null` and linked `users.display_name = crinx7`, when messages are chunked, then the chunk text starts with `crinx7:` and metadata author is `crinx7`.
- AE2. **Covers R3.** Given `crinx7` exists only as a display name, when `draft-context --user crinx7` runs, then target history includes that user's messages.
- AE3. **Covers R4, R16, R17.** Given indexed Telegram evidence authored by display-name `crinx7`, when the operator searches `crinx7` or `@crinx7`, then that evidence is boosted ahead of unrelated semantic results.
- AE4. **Covers R18.** Given another user's message text mentions `crinx7`, when the author is not `crinx7`, then that text mention is not treated as an author exact match.
- AE5. **Covers R5, R6.** Given a Telegram window contains empty messages, when chunks are built, then those empty messages do not appear as blank `author:` or `unknown:` lines in searchable text.
- AE6. **Covers R8, R9, R10, R11.** Given a Chinese Telegram message is ingested and translated, when the operator searches an English equivalent, then search can return the original Telegram evidence with translated helper context.
- AE7. **Covers R12, R13, R14.** Given the target support user wrote in Chinese, when the Agent Surface drafts a reply, then the proposed reply is in Chinese while evidence may include English helper translation for the operator.
- AE8. **Covers R15.** Given the target language cannot be inferred confidently, when the Agent Surface drafts a reply, then it shows the language assumption before the Support Operator confirms posting.

---

## Scope Boundaries

- This does not create fuzzy display-name search.
- This does not create a separate user-profile lookup UI.
- This does not change Manual Knowledge truth or conflict semantics.
- This does not change vector retrieval behavior.
- This does not replace original Telegram text with translated text.
- This does not require automatic translation before display-name author retrieval can ship.

---

## Success Criteria

- Visible Telegram display-name authors are not lost as `unknown` in chunks.
- Empty Telegram messages do not create noisy searchable author-only lines.
- `search crinx7` retrieves the local support exchange when `crinx7` is stored as a display name.
- Non-English Telegram support requests can be searched through original text and, when available, English helper translation.
- Draft replies preserve the Support User's original language when that language can be inferred.
- `draft-context --user crinx7` no longer reports missing user history when matching display-name-authored messages exist.

---

## Sources / Research

- `tg_support/telegram_client.py` stores sender username in `author_username` and sender first name/title in `author_name`.
- `tg_support/storage/db.py` stores `author_name` as `users.display_name`, but `telegram_documents_by_author_username` currently matches only `messages.author_username`.
- `tg_support/indexing/chunking.py` currently renders `unknown:` when `messages.author_username` is null.
- `tg_support/support/context.py` currently finds user history only by `messages.author_username`.
