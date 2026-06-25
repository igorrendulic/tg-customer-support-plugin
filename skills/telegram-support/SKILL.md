---
name: telegram-support
description: Use the local Telegram support corpus to answer support analytics questions, prepare evidence-backed reply drafts, and post only after explicit operator confirmation.
---

# Telegram Support

Use this skill when the operator asks about a configured Telegram support chat, wants a draft answer for a user or message, or wants to post a previously approved reply.

## CLI

Run commands through the bundled local helper. Resolve the helper relative to this skill's plugin root; from this file that is `../../scripts/tg-support`. If the operator is developing from a source checkout, `scripts/tg-support` from the repo root is equivalent.

```bash
<plugin-root>/scripts/tg-support --profile default <command>
```

The first run bootstraps the Python runtime under the operator's local data directory unless `TG_SUPPORT_VENV` overrides it.

The CLI prints JSON. Treat that JSON as the source of truth for local corpus state, evidence, conflict checks, draft IDs, and confirmation tokens.

## Setup Preflight

Before answering analytics questions, searching, drafting, or posting, run:

```bash
<plugin-root>/scripts/tg-support --profile default status
```

If `ok` is false, do not continue into the normal workflow. Use `next_action` to guide the operator through the missing setup step:

- `setup`: ask for a Telegram chat identifier and at least one website or blog seed, then run `setup`.
- `credentials`: explain that Telegram API ID and API hash are needed from `https://my.telegram.org`, then run `credentials --api-id <id> --api-hash-stdin` and provide the hash on stdin after the operator provides it.
- `login`: run `login` so the operator can complete the local Telethon user-session login.
- `sync`: run `sync` to pull Telegram history.
- `crawl`: run `crawl` to fetch configured website or blog resources.
- `index`: run `index` to build the local retrieval index.
- `ready`: proceed with the requested support workflow.

After each setup command, run `status` again and continue from the new `next_action`. Never print or repeat the API hash back to the operator.

Repository Evidence is optional. If status includes configured repository details, use them only for product-behavior, capability, API-behavior, or debugging questions. If no repository is configured, normal Telegram, web, and Manual Knowledge workflows remain ready.

## Manual Knowledge

When the operator asks to save durable support knowledge, extract the note text, effective date, optional expiry date, and caveats from the conversation. Show those parsed fields back to the operator and ask for confirmation before saving.

After confirmation, run:

```bash
<plugin-root>/scripts/tg-support --profile default knowledge-add --text <text> --effective-date <YYYY-MM-DD>
```

Add `--expires-date <YYYY-MM-DD>` and `--caveats <text>` when present. If the operator revises or cancels the parsed fields, do not run `knowledge-add` until they confirm the corrected note.

When `search` or `draft-context` returns Manual Knowledge Note evidence, include it in the evidence summary. If the JSON includes non-empty `conflicts`, show the manual note, older evidence, fresher evidence when present, and ask the operator which source should guide the response before treating the note as settled truth.

## Repository Evidence

For questions about what the product supports, how an API behaves, why a user can or cannot do something, or likely debugging causes, run:

```bash
<plugin-root>/scripts/tg-support --profile default repo-evidence "<query>"
```

Use Repository Evidence from the configured branch as the highest-priority support truth. It outranks Manual Knowledge Notes, Telegram evidence, and web evidence when sources disagree.

If `repository_evidence.warning` is present, show it before relying on the code evidence. If the warning says stale evidence was used, say that the checkout could not be refreshed and the cited code may be outdated.

Do not run repository lookup for normal analytics or drafting questions that do not depend on product behavior. Do not create Manual Knowledge Notes, modify code, create branches, or open pull requests from repository findings unless the operator starts a separate explicit workflow.

## Safety Boundary

Never post to Telegram directly from agent reasoning. A Telegram write is allowed only after:

1. `draft-context`, `repo-evidence`, or another retrieval command has produced needed evidence and any returned `conflicts` or stale repository warnings are shown to the operator.
2. The operator has seen the exact target chat, target user or message ID when available, exact message text, and evidence summary.
3. The operator explicitly replies with `post` for that exact message and target.
4. The CLI confirmation command succeeds.

If the operator says `cancel`, use the cancel confirmation token or leave the draft unposted. Do not silently retry duplicate posts.

## Workflows

- For reply drafting, follow `references/reply-workflow.md`.
- For analytics questions, follow `references/analytics-workflow.md`.
