# Concepts

Shared domain vocabulary for this project -- entities, named processes, and status concepts with project-specific meaning. Seeded with core domain vocabulary, then accretes as ce-compound and ce-compound-refresh process learnings; direct edits are fine. Glossary only, not a spec or catch-all.

## Telegram Support Agent

### Support Operator
The local human operator who owns the Telegram account, local profile data, evidence review, draft approval, and final post/cancel decision.

### Agent Surface
A Codex, Claude, or other agent-facing wrapper that guides the operator workflow while delegating product behavior to the shared local core.

### Local Core
The shared implementation boundary that owns Telegram access, crawling, storage, indexing, retrieval, analytics, drafting records, and confirmed posting for every agent surface.

### Support Profile
The operator-owned local state boundary for one configured support workflow, including configuration, Telegram session state, SQLite data, and rebuildable indexes.

### Ready Profile
A Support Profile that has the required configuration, profile-local Telegram credentials, a usable Telegram session, synced Telegram history, crawled web seeds, and built indexes for normal support workflows.

### Evidence Bundle
The source-linked retrieval result set an agent uses to answer analytics questions or prepare a reply draft.

### Draft
The exact proposed Telegram reply persisted before posting, together with its target, evidence, status, and confirmation choices.

### Confirmation Token
An action-specific token representing an explicit operator choice to post or cancel one persisted Draft.

### Post Attempt
The recorded outcome of applying a Confirmation Token, whether posted, cancelled, or failed.

## Relationships

A Support Operator uses an Agent Surface, but the Agent Surface calls the Local Core rather than owning support behavior. The Local Core reads and writes a Support Profile. Evidence Bundles inform Drafts, Drafts create Confirmation Tokens, and applying a Confirmation Token produces a Post Attempt.
