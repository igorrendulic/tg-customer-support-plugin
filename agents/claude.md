# Telegram Support Agent For Claude

This companion surface uses the same local CLI as the Codex plugin. It does not duplicate retrieval or posting logic.

## Setup

```bash
scripts/tg-support setup --chat <telegram-chat> --seed <website-or-blog-url>
scripts/tg-support login
scripts/tg-support sync
scripts/tg-support crawl
scripts/tg-support index
```

## Analytics

Use `scripts/tg-support stats <kind>` for direct counts and `scripts/tg-support search "<query>"` for evidence-heavy questions. Preserve returned source references in answers. If `conflicts` is non-empty, ask the operator which source should guide the answer before resolving the conflict.

## Manual Knowledge

When the operator asks to save durable support knowledge, show the parsed note text, effective date, optional expiry date, and caveats before saving. After confirmation, use `scripts/tg-support knowledge-add --text "<note>" --effective-date <YYYY-MM-DD>` with optional `--expires-date` and `--caveats`.

## Replies

Use `scripts/tg-support draft-context --user <username>` or `--message-id <id>`. Show any returned conflicts before drafting. Show the exact reply text and evidence to the operator, then create and confirm a draft only after the operator explicitly says `post`.
