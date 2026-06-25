---
name: telegram-support
description: Use the local Telegram support corpus to answer support analytics questions, prepare evidence-backed reply drafts, and post only after explicit operator confirmation.
---

# Telegram Support

Use this skill when the operator asks about a configured Telegram support chat, wants a draft answer for a user or message, or wants to post a previously approved reply.

## CLI

Run commands through the local helper:

```bash
scripts/tg-support --profile default <command>
```

The CLI prints JSON. Treat that JSON as the source of truth for local corpus state, evidence, draft IDs, and confirmation tokens.

## Safety Boundary

Never post to Telegram directly from agent reasoning. A Telegram write is allowed only after:

1. `draft-context` or another retrieval command has produced evidence.
2. The operator has seen the exact target chat, target user or message ID when available, exact message text, and evidence summary.
3. The operator explicitly replies with `post` for that exact message and target.
4. The CLI confirmation command succeeds.

If the operator says `cancel`, use the cancel confirmation token or leave the draft unposted. Do not silently retry duplicate posts.

## Workflows

- For reply drafting, follow `references/reply-workflow.md`.
- For analytics questions, follow `references/analytics-workflow.md`.
