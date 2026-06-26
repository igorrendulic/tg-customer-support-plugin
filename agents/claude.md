# Telegram Support Agent For Claude

This companion surface uses the same local CLI as the Codex plugin. It does not duplicate retrieval or posting logic.

## Setup

```bash
scripts/tg-support setup --chat <telegram-chat> [--seed <website-or-blog-url>] [--operator <identity>]
scripts/tg-support login
scripts/tg-support sync
scripts/tg-support crawl
scripts/tg-support index
```

## Analytics

Use `scripts/tg-support stats <kind>` for direct counts and `scripts/tg-support search "<query>"` for evidence-heavy questions. Preserve returned source references in answers. If `conflicts` is non-empty, ask the operator which source should guide the answer before resolving the conflict.

When search returns Support Exchange evidence, keep requester, configured operator reply, peer/community reply, and unanswered roles separate. Treat operator replies as support evidence; peer/community replies are context unless corroborated by authoritative evidence.

For product-behavior, capability, API-behavior, or debugging questions, use `scripts/tg-support repo-evidence "<query>"`. Repository Evidence from the configured branch outranks Manual Knowledge Notes, Telegram evidence, and web evidence. Show any stale checkout warning before relying on repository evidence.

## Manual Knowledge

When the operator asks to save durable support knowledge, show the parsed note text, effective date, optional expiry date, and caveats before saving. After confirmation, use `scripts/tg-support knowledge-add --text "<note>" --effective-date <YYYY-MM-DD>` with optional `--expires-date` and `--caveats`.

## Replies

Use `scripts/tg-support draft-context --user <username>` or `--message-id <id>`. Show any returned conflicts before drafting.

When `draft-context` returns `evidence_sufficiency`, show its state and reasons with the evidence summary. If `direct_answer_supported` is false, or Repository Evidence has a stale warning, present two options before creating a draft: a cautious evidence-limited answer and a DM follow-up asking only for the missing support-blocking information. Do not save the DM follow-up wording as Manual Knowledge or cite it as evidence.

When `draft-context` returns Support Exchange evidence, show the requester/operator/peer/community roles before drafting. Peer/community and unanswered exchange evidence should trigger an evidence-limited posture unless another authoritative source supports the answer.

When `draft-context` returns `fuzzy_author_candidates`, show them as disambiguation options only. Do not treat fuzzy candidates as target history until the operator chooses or reruns with an exact username/display name.

When `draft-context` returns `target.language`, draft in that language unless the operator asks otherwise. Use `translated_text` only as helper context for understanding evidence, not as support truth and not as a reason to answer in English.

Show the exact selected reply text and evidence to the operator, then create and confirm a draft only after the operator explicitly says `post`.
