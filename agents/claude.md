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

Use `scripts/tg-support stats <kind>` for direct counts and `scripts/tg-support search "<query>"` for evidence-heavy questions. Preserve returned source references in answers.

## Replies

Use `scripts/tg-support draft-context --user <username>` or `--message-id <id>`. Show the exact reply text and evidence to the operator, then create and confirm a draft only after the operator explicitly says `post`.
