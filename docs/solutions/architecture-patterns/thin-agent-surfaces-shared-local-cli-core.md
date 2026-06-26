---
title: "Thin agent surfaces over a shared local CLI core"
date: 2026-06-25
category: architecture-patterns
module: telegram-support-agent
problem_type: architecture_pattern
component: assistant
severity: medium
applies_when:
  - "Building agent plugin or companion surfaces that need access to local services or external write APIs"
  - "Adding Telegram, crawling, retrieval, statistics, drafting, or posting behavior to the support workflow"
  - "Maintaining write safety by requiring deterministic confirmation tokens before externally visible Telegram posts"
related_components:
  - tooling
  - service_object
  - database
  - development_workflow
tags:
  - telegram-support
  - agent-surfaces
  - shared-cli
  - local-python-core
  - confirmation-gates
  - posting-safety
  - retrieval
  - sqlite-fts5
  - sqlite-vec
  - bge-m3
---

# Thin agent surfaces over a shared local CLI core

## Context

The Telegram support agent is a local-first plugin, not a hosted helpdesk or an MCP server. The reusable product boundary is the local Python package and CLI in `tg_support/` plus `scripts/tg-support`; Codex and Claude are thin operator surfaces that call that CLI and enforce workflow rules.

This split keeps three concerns separate:

- Local Telegram/session access, website crawling, SQLite storage, chunking, retrieval, statistics, draft records, and posting are deterministic product behavior.
- Codex and Claude integration files are orchestration surfaces that tell an agent which local command to run and how to present the result.
- Telegram posting is an externally visible write, so it needs a hard confirmation boundary in code and tests, not only a prompt instruction.

Session history reinforced that this was a deliberate architecture decision, not incidental implementation convenience. Earlier planning excluded MCP, rejected reuse of an already logged-in Telegram app session, and kept the first version focused on a single local operator with one local Telegram client session and local data store. (session history)

The repo reflects that split. `scripts/tg-support` shells into `python3 -m tg_support.cli`, and `pyproject.toml` exposes `tg-support = "tg_support.cli:main"`. The Codex skill in `skills/telegram-support/SKILL.md`, the Claude companion in `agents/claude.md`, and the OpenAI surface in `agents/openai.yaml` all refer back to the same commands instead of duplicating business logic.

## Guidance

Keep the local Python CLI/core as the shared boundary. New capabilities should land in `tg_support/` first, be exposed through `tg_support.cli`, and then be referenced by Codex/Claude skill text. Do not add separate retrieval, posting, or state-machine logic in `skills/` or `agents/`.

The current command boundary is a good model:

```text
scripts/tg-support --profile default setup --chat <chat> --seed <url>
scripts/tg-support --profile default sync
scripts/tg-support --profile default crawl
scripts/tg-support --profile default index
scripts/tg-support --profile default search "<query>"
scripts/tg-support --profile default stats <kind>
scripts/tg-support --profile default draft-context --user <username>
scripts/tg-support --profile default draft-create --text "<exact reply>" --message-id <id>
scripts/tg-support --profile default confirm <post_or_cancel_token>
```

The CLI prints JSON, and the skills treat that JSON as the source of truth for profile state, evidence, draft IDs, and confirmation tokens. This keeps agent behavior inspectable: the agent can summarize and draft, but it does not own canonical state.

Persist local state in the profile directory and SQLite, not in plugin source files or agent memory. `tg_support.config` resolves a profile under `TG_SUPPORT_HOME` or `~/.tg-support/profiles/<profile>`, with `support.sqlite3` and `telegram.session` as profile-local artifacts. `tests/test_config.py::test_config_stores_profile_outside_source_tree` and `tests/test_cli_setup.py::test_cli_setup_stores_normalized_config` prove setup normalizes a Telegram chat identifier and writes profile config through the local profile path rather than hard-coding a project-specific location.

Use SQLite as the durable metadata source and treat indexes as rebuildable projections. `tg_support/storage/schema.py` owns tables for chats, users, messages, pages, chunks, indexed documents, index runs, drafts, confirmations, and post attempts. Retrieval can be rebuilt from source chunks and index metadata, but source records must remain traceable. `tests/test_storage.py::test_chunk_records_trace_to_sources` proves chunk records point back to Telegram or web sources, and `tests/test_storage.py::test_index_run_does_not_delete_source_records` proves recording an index run does not delete source messages.

Keep retrieval local and source-linked. `tg_support/indexing/chunking.py` chunks web pages with URL/title metadata and Telegram messages with neighboring conversation context. `tg_support/indexing/hybrid.py` combines lexical and vector results with reciprocal rank fusion and returns chunk/source identifiers, text, scores, and metadata. `tests/test_chunking.py::test_telegram_chunks_include_neighboring_context`, `tests/test_hybrid_retrieval.py::test_hybrid_search_returns_source_references`, and `tests/test_hybrid_retrieval.py::test_rrf_favors_items_in_both_result_sets` cover the behavior that lets agents cite evidence without guessing provenance.

For the SQLite Hybrid Search Index, keep three separate contracts explicit:

- `documents` is the canonical retrieval projection for source-linked chunk text and metadata.
- `fts_documents` is the SQLite FTS5 projection for exact product, policy, command, and error terms.
- `vec_documents` is the sqlite-vec projection for 384-dimensional `BAAI/bge-small-en-v1.5` semantic embeddings.

Those tables should be rebuilt together from the same source chunks. Do not accept arbitrary embedding models unless the storage schema and query path validate compatible dimensions; the sqlite-vec table shape is part of the schema contract. FTS tokenization should preserve the punctuation that matters to support search, including hyphenated and underscored product or policy names, so exact operational terms do not depend on vector recall.

Index freshness needs a content-level signature, not only a high-water mark. A max chunk id catches appended content, but it misses edited source text, metadata corrections, and re-chunking that reuses existing identities. Store a deterministic signature of the indexed chunk payload in `index_runs`, compare it before search, and fail with an actionable rebuild response when it drifts.

Treat retrieval setup failures as structured CLI errors. Missing sqlite-vec support, embedding model load failures, encode failures, unsupported embedding configuration, and unbuilt indexes should reach `search` and `draft-context` as JSON with a clear next action and useful diagnostics such as the SQLite version. Returning empty search results for an unusable index hides setup bugs and leads agents to answer without evidence.

Make posting a separate confirmation-gated state transition. The reply workflow should be:

1. Retrieve context with `draft-context`.
2. Agent drafts natural-language text from returned history, thread, and evidence.
3. Store the exact proposed message with `draft-create`, which creates one post token and one cancel token in `confirmations`.
4. Show the operator the target chat, target user/message, exact message text, reply mode, and evidence.
5. Only after the operator says `post` or `cancel`, run `confirm <token>`.

The implementation puts this boundary in `tg_support/support/drafting.py` and `tg_support/support/posting.py`. `create_draft` persists the exact message and evidence, then creates separate post and cancel tokens. `apply_confirmation` looks up a token, rejects unknown or already consumed tokens, records cancellation without sending, requires a reply target for posts, and sends through the Telegram gateway only for a valid post confirmation.

Preserve these regression anchors when changing the posting path:

- `tests/test_posting_confirmation.py::test_cancelled_draft_does_not_send` proves the cancel token records cancellation and never calls `send_reply`.
- `tests/test_posting_confirmation.py::test_confirmed_draft_sends_once` proves a valid post token sends exactly one Telegram reply and duplicate use is rejected.
- `tests/test_posting_confirmation.py::test_post_without_reply_target_fails` proves the CLI does not silently fall back to a normal Telegram message when no reply target exists.
- `tests/test_posting_confirmation.py::test_missing_gateway_does_not_consume_post_token` proves infrastructure failure before a gateway exists does not burn the operator's post token.

Session history also captured two concrete guardrails that should stay with this architecture: setup validation should return machine-readable JSON instead of letting argparse exit early, and missing Telegram gateway errors must not consume a post token. (session history)

Confirmation tokens are CLI inputs, so make them parser-safe. Random tokens can accidentally begin with option-looking text; action-prefixed tokens such as `post_...` and `cancel_...` avoid argparse ambiguity while still preserving the explicit confirmation boundary.

The skill and companion docs should stay declarative and thin. `skills/telegram-support/SKILL.md` says never post from agent reasoning and requires evidence, target display, explicit `post`, and a successful CLI confirmation. `skills/telegram-support/references/reply-workflow.md` describes the operator-facing steps. `agents/claude.md` explicitly says the Claude surface uses the same local CLI and does not duplicate retrieval or posting logic.

## Why This Matters

The shared CLI/core boundary prevents divergence between agent surfaces. If Codex and Claude each learned their own way to search, draft, or post, safety and retrieval quality would depend on prompt wording instead of product behavior. By routing both surfaces through `scripts/tg-support`, fixes to ingestion, indexing, evidence formatting, drafts, and confirmation immediately apply to every supported agent.

The local persisted state model also fits the privacy and distribution requirements. Telegram sessions, support history, crawled pages, indexes, drafts, confirmation tokens, and post attempts are operator-owned local data. They should not be checked into the plugin, hidden in agent transcripts, or spread across separate integration-specific stores.

Hybrid retrieval only improves support answers when both success and failure modes are trustworthy. FTS5 recovers exact product and policy terms, sqlite-vec broadens recall for natural-language phrasing, and BGE Small keeps embedding local. The surrounding guardrails matter just as much as the ranking path: stale indexes, missing runtime extras, unsupported dimensions, or swallowed model errors all produce plausible but incomplete evidence unless the CLI fails loudly.

The explicit posting boundary is the most important safety property. A support agent can be useful while still being allowed to reason only up to "here is the exact reply I propose." The deterministic CLI owns "this exact draft was confirmed for this exact target and was posted once." That distinction keeps agent creativity out of the external write path and gives tests a concrete behavior to assert.

## When to Apply

Apply this pattern when building agent plugins that combine local private state, retrieval, and externally visible actions. It is especially relevant when more than one agent surface should reuse the same behavior, such as Codex skills, Claude companion commands, or future wrappers.

Use the shared CLI/core approach when:

- The integration must support both Codex and Claude without assuming identical plugin mechanics.
- The system needs local credentials or private local data, such as Telegram sessions and support history.
- Retrieval results must include source metadata that an agent can cite.
- Exact product, policy, command, or error terms must be recovered alongside semantic matches.
- Local embeddings or SQLite extensions may fail on user machines and need actionable CLI diagnostics.
- The final action changes an external system and must be gated by explicit operator confirmation.
- Tests need to prove safety properties independently of agent prompt behavior.

Do not move the confirmation boundary into prose instructions alone. Prompt instructions are still useful for operator flow, but the code must reject duplicate tokens, missing reply targets, and unconfirmed posts.

## Examples

A good feature addition follows the existing layering. For example, adding a new "common complaint clusters" analytics command should add query/index logic under `tg_support/support/` or `tg_support/indexing/`, expose it in `tg_support.cli` as JSON, and then update `skills/telegram-support/references/analytics-workflow.md` to tell the agent when to call it. The skill should not implement clustering in markdown instructions or ask the model to infer clusters from raw SQLite records.

A good reply flow keeps source traceability and confirmation separate:

```text
Agent -> CLI: draft-context --message-id 123
CLI -> Agent: target, nearby thread, user history, evidence chunks with source metadata
Agent -> Operator: exact proposed reply plus evidence summary
Agent -> CLI: draft-create --message-id 123 --text "<exact proposed reply>"
CLI -> Agent: draft_id, post_token, cancel_token
Operator -> Agent: post
Agent -> CLI: confirm <post_token>
CLI -> Telegram: send_reply(chat, exact_text, reply_to_message_id=123)
```

The inverse is the anti-pattern:

```text
Agent retrieves context, drafts text, and calls Telegram directly because the operator's wording sounded approving.
```

That bypasses the persisted draft, skips the confirmation token, loses post-attempt auditability, and makes duplicate-send behavior hard to test.

The current storage schema shows how to preserve auditability without overcomplicating the first version. `drafts` stores the target, exact message text, evidence, and status. `confirmations` stores action-specific tokens with `consumed_at`. `post_attempts` records posted, cancelled, or failed outcomes and the Telegram message ID or error. That is enough to answer "what did we show, what did the operator choose, and what happened?"

The crawler/retrieval path follows the same local-source principle. `crawl` stores web pages in `pages`; chunking creates web chunks with URL/title metadata and Telegram chunks with chat/message/author/timestamp metadata; `index` writes `documents`, FTS5 rows, sqlite-vec rows, and an `index_runs` row with the indexed source signature. Agent-facing answers should cite those returned references, not memory or hidden assumptions.

The SQLite hybrid index also has a few anti-patterns worth testing directly:

```text
Search returns no results because sqlite-vec failed to load, but the CLI reports success.
```

That turns a setup problem into a false negative evidence bundle. The command boundary should return a dependency error with the next action.

```text
Search reports the index as current because the max chunk id is unchanged after a page edit.
```

That serves stale policy text while looking healthy. Freshness checks should compare indexed content signatures.

```text
A different embedding model is accepted even though the vector table is fixed to BGE Small dimensions.
```

That moves an invalid configuration from setup time to query time. Reject it before indexing or searching.

## Related

- `docs/brainstorms/telegram-support-agent-requirements.md` defines the original local-first, explicit-confirmation requirements.
- `docs/plans/2026-06-25-001-feat-telegram-support-agent-plugin-plan.md` records the architecture decisions: shared Python core, no MCP in v1, SQLite as source of truth, local retrieval adapters, and confirmation-gated posting.
- `docs/setup.md` documents local profile state, setup, indexing, optional adapters, and reset behavior.
- `docs/claude-usage.md` documents the Claude companion surface.
- `skills/telegram-support/SKILL.md` is the Codex-facing safety contract.
- `skills/telegram-support/references/reply-workflow.md` is the concrete reply workflow agents should follow.
- `agents/claude.md` and `agents/openai.yaml` are thin surfaces over the same CLI.
- `tg_support/cli.py`, `tg_support/config.py`, `tg_support/storage/schema.py`, `tg_support/indexing/hybrid.py`, `tg_support/indexing/lexical.py`, `tg_support/indexing/vector.py`, `tg_support/indexing/embeddings.py`, `tg_support/support/drafting.py`, and `tg_support/support/posting.py` are the core files to inspect before changing command, retrieval, or posting semantics.
- `tests/test_posting_confirmation.py`, `tests/test_storage.py`, `tests/test_hybrid_retrieval.py`, `tests/test_chunking.py`, `tests/test_config.py`, and `tests/test_cli_setup.py` are the regression anchors for the architecture. Preserve coverage for exact-term retrieval, sqlite-vec dependency failures, embedding load and encode failures, stale index signatures, unsupported retrieval config, CLI-safe confirmation tokens, and JSON readiness errors.
