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

- `setup`: ask for a Telegram chat identifier, whether to add optional website or blog seed URLs, whether to add optional GitHub repository evidence configuration, and whether to add optional operator identities for authoritative support replies. Tell the operator they can skip seed setup, skip repository setup, and skip operator identity setup. If repository evidence is provided, pass the repository as `--repository <owner/repo-or-url-or-path>` and the branch as `--repository-branch <branch>` only when the operator provides one; the CLI defaults the branch to `main` when omitted. If operator identities are provided, pass each as a repeated `--operator <identity>`. Then run `setup`.
- `credentials`: explain that Telegram API ID and API hash are needed from `https://my.telegram.org`, then run `credentials --api-id <id> --api-hash-stdin` and provide the hash on stdin after the operator provides it.
- `login`: run `login` so the operator can complete the local Telethon user-session login.
- `sync`: run `sync` to pull Telegram history.
- `crawl`: run `crawl` to fetch configured website or blog resources.
- `index`: run `index` to build the local retrieval index.
- `ready`: proceed with the requested support workflow.

After each setup command, run `status` again and continue from the new `next_action`. Never print or repeat the API hash back to the operator.

Repository Evidence is optional. If status includes configured repository details, use them only for product-behavior, capability, API-behavior, or debugging questions. If no repository is configured, normal Telegram, web, and Manual Knowledge workflows remain ready.

## Support Exchanges

`index` derives Support Exchange records from Telegram history. A Support Exchange is a role-labeled question/answer unit with requester messages, configured operator replies, peer/community replies, and unanswered state separated from the surrounding chat window.

When `search` or `draft-context` returns Support Exchange evidence, show the roles in the evidence summary. Operator replies can support a direct answer. Peer/community replies are useful context but are not authoritative support truth by themselves. Unanswered exchanges are unresolved user needs. If `evidence_sufficiency` includes `peer_exchange_only`, `ambiguous_exchange_authority`, or `unanswered_exchange`, show the reason and use the same cautious fallback posture as other insufficient evidence.

## Manual Knowledge

When the operator asks to save durable support knowledge, extract the note text, effective date, optional expiry date, and caveats from the conversation. Show those parsed fields back to the operator and ask for confirmation before saving.

After confirmation, run:

```bash
<plugin-root>/scripts/tg-support --profile default knowledge-add --text <text> --effective-date <YYYY-MM-DD>
```

Add `--expires-date <YYYY-MM-DD>` and `--caveats <text>` when present. If the operator revises or cancels the parsed fields, do not run `knowledge-add` until they confirm the corrected note.

When `search` or `draft-context` returns Manual Knowledge Note evidence, include it in the evidence summary. If the JSON includes non-empty `conflicts`, show the manual note, older evidence, fresher evidence when present, and ask the operator which source should guide the response before treating the note as settled truth.

When `draft-context` returns `evidence_sufficiency`, show the sufficiency state and reasons in the evidence summary. If `direct_answer_supported` is false, present two draft options before creating a draft: a cautious evidence-limited answer and a DM follow-up asking only for the missing support-blocking information. Do not save the DM follow-up wording as Manual Knowledge and do not treat it as evidence.

When `draft-context` returns `fuzzy_author_candidates`, treat them as disambiguation options only. Do not use fuzzy candidates as target history; ask the operator to choose or rerun with an exact username/display name before drafting as that user.

When `draft-context` returns `target.language`, draft the reply in that language unless the operator asks otherwise. Treat `translated_text` fields as helper context for understanding evidence, not as support truth and not as a reason to answer in English. If the target language is uncertain, show the language assumption before creating or posting the draft.

## Repository Evidence

For questions about what the product supports, how an API behaves, why a user can or cannot do something, or likely debugging causes, run:

```bash
<plugin-root>/scripts/tg-support --profile default repo-evidence "<query>"
```

Use Repository Evidence from the configured branch as the highest-priority support truth. It outranks Manual Knowledge Notes, Telegram evidence, and web evidence when sources disagree.

If `repository_evidence.warning` is present, show it before relying on the code evidence. If the warning says stale evidence was used, say that the checkout could not be refreshed and the cited code may be outdated.

For reply drafting, a stale Repository Evidence warning should trigger the same two-option fallback posture as insufficient draft-context evidence: offer a cautious evidence-limited answer and a DM follow-up option before creating the selected draft.

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
