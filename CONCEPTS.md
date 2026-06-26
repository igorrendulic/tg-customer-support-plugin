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
A Support Profile that has the required configuration, profile-local Telegram credentials, a usable Telegram session, synced Telegram history, any configured optional sources prepared, and built indexes for normal support workflows.

### Evidence Bundle
The source-linked retrieval result set an agent uses to answer analytics questions or prepare a reply draft, including any Manual Knowledge Notes that influence the answer.

### Evidence Sufficiency
The support-drafting judgment that collected evidence is strong enough to support a direct reply without pretending missing, weak, conflicting, stale, vague, or account-specific context is known.

### Fallback Draft Option
An operator-visible draft alternative generated when evidence is insufficient, such as a cautious limited answer or a request for the Support User to provide missing private or account-specific information by DM. Fallback Draft Options shape replies but are not support truth.

### Manual Knowledge Note
A Support Operator-confirmed local corpus entry for dated support facts, policy changes, operational caveats, or other durable knowledge that may override or reinterpret older Telegram and web evidence within an effective or expiry window.

### Repository Evidence
Read-only, profile-local evidence gathered from a configured GitHub repository and branch during product-behavior or debugging support questions. Repository Evidence from the configured branch outranks Manual Knowledge Notes, Telegram evidence, and web evidence when sources disagree.

### SQLite Hybrid Search Index
The Support Profile-local retrieval projection that combines SQLite FTS5 exact-term search, sqlite-vec vector search, and local `BAAI/bge-small-en-v1.5` embeddings over source-linked indexed documents.

### Username Exact Match Boost
The search-ranking behavior where an exact Telegram author username query is treated as a strong evidence signal, while still returning source-linked Telegram message or context evidence rather than a standalone user record.

### Conflict Check
The retrieval-time safety step that compares an applicable Manual Knowledge Note against indexed Telegram or web evidence, re-queries fresher evidence when needed, and asks the Support Operator before resolving contested support truth.

### Draft
The exact proposed Telegram reply persisted before posting, together with its target, evidence, status, and confirmation choices.

### Confirmation Token
An action-specific token representing an explicit operator choice to post or cancel one persisted Draft.

### Post Attempt
The recorded outcome of applying a Confirmation Token, whether posted, cancelled, or failed.

## Relationships

A Support Operator uses an Agent Surface, but the Agent Surface calls the Local Core rather than owning support behavior. The Local Core reads and writes a Support Profile. Repository Evidence can appear in Evidence Bundles for product-behavior or debugging questions. Manual Knowledge Notes can appear in Evidence Bundles after Conflict Checks. Evidence Bundles inform Evidence Sufficiency, Drafts, and Fallback Draft Options. Drafts create Confirmation Tokens, and applying a Confirmation Token produces a Post Attempt.
