# Telegram Support Agent Plugin Requirements

Date: 2026-06-25

## Summary

Create an installable agent plugin/workflow for Codex, with a Claude-compatible companion path, that helps a single support operator answer questions in a configured Telegram support chat. The agent should ingest Telegram history and the operator's public website/blog resources into a local retrieval store, answer operational questions about the support chat, draft responses for specific users, and post replies only after explicit confirmation.

The plugin is distributed for others to install, but each installation is local and personal: every operator logs into Telegram once, indexes their own configured chat and project resources, and owns their own local database/session.

## Primary User

An owner/operator who currently:

- Reads Telegram support messages manually.
- Asks ChatGPT to draft answers using remembered support context.
- Iterates on the answer.
- Adds links to relevant website, blog, or external documentation resources.
- Copies the final answer into Telegram as a reply.

The first version is optimized for one support person, not a multi-agent helpdesk team.

## Core Goals

- Replace manual context gathering with local search over Telegram history and indexed public resources.
- Draft high-quality support replies for a specific Telegram user or message.
- Require an explicit confirmation before posting anything to Telegram.
- Support analytical questions such as common complaints, most helpful users, message volume, and top posters.
- Keep setup simple enough to feel like: install plugin, run setup with a Telegram chat handle/link, log in once, and index data.
- Avoid MCP as the integration mechanism.

## Required First-Version Flows

### Setup

The setup command accepts a Telegram chat identifier such as `channel-name`, `@channel-name`, or `t.me/channel-name`. It must not hard-code any specific project or chat.

Setup should:

- Start a one-time local Telegram login.
- Store the Telegram session locally.
- Resolve the configured chat and detect its type.
- Pull an initial configurable history window.
- Crawl the configured website/blog resources.
- Build local search indexes.
- Store metadata and source references in SQLite.
- Leave the system ready for Codex/Claude prompts.

### Draft Reply

The operator asks for help answering a user or message, for example:

`Prepare answer for @someuser`

The agent should:

- Read the user's recent support history.
- Retrieve similar past issues and useful prior answers.
- Retrieve relevant website/blog/resource pages.
- Prepare a response with source-grounded links where useful.
- Show the proposed response and the evidence used.
- Ask for explicit `post` or `cancel` confirmation.
- If confirmed, post as a Telegram reply where possible.

### Freeform Support Questions

The operator can ask arbitrary questions over the local corpus, such as:

- What is the most common complaint in the last month?
- Who helps other users the most?
- What changed in support questions after a release?
- Which questions keep requiring the same website link?

The agent should retrieve relevant data, summarize it, and expose enough citations/metadata for the operator to trust the answer.

### CLI Statistics

The tool should support direct stats-style commands for fast answers, including:

- Number of posts/messages since a given date.
- Most active users.
- Most replied-to users.
- Most common repeated topics or complaint clusters.
- Links most often used in responses.

## Knowledge Sources

### Telegram

Telegram history is the primary behavioral corpus. It contains user questions, prior support answers, helper behavior, timestamps, usernames, and message relationships.

The system should treat the configured Telegram target generically as a chat and detect whether it is a group/supergroup, broadcast channel, linked discussion, or another accessible Telegram entity.

### Website And Blog

The website/blog crawler is a first-class setup task, not a later add-on. Crawled pages are canonical support resources and should be stored with source URL, title, timestamps, extracted text, and chunk references.

The crawler should support seed URLs and reasonable scope controls so another user can use the plugin for their own project.

### External Docs

External resources such as passkey documentation may be included through the crawler or explicit configured URLs. They should be cited by URL when used in a draft.

## Retrieval Requirements

The local retrieval layer should combine:

- BM25 or sparse lexical retrieval.
- Dense vector retrieval.
- Reciprocal rank fusion or equivalent hybrid ranking.
- SQLite metadata linking each retrievable item back to source type, source ID, URL/message, author, timestamp, chat, and chunk.

Chunking should be used when messages, webpages, or conversations are too large to retrieve accurately as single units. Telegram conversations should preserve enough surrounding context to avoid quoting isolated messages without their thread/reply context.

The embedding model should run locally. The implementation should choose a strong current Hugging Face-compatible embedding model for support/chat retrieval, with the model configurable so it can be upgraded without reworking the stored metadata model.

Qdrant Edge is a plausible vector-store direction because it is an embedded, local vector search engine with in-process storage and on-device embedding/BM25 guidance, but the final library choice belongs in implementation planning.

## Safety And Confirmation

Posting to Telegram is in scope, but every write must require explicit confirmation.

The confirmation UI must show:

- The target chat.
- The target user/message if available.
- The exact message that will be posted.
- Whether it will be a reply or a normal message.
- A clear `post` and `cancel` path.

The tool must not silently post, auto-retry duplicate posts, or use broad autonomous write behavior.

## Distribution Shape

Codex should receive an installable plugin with one or more skills and local helper scripts/CLIs. The plugin should be installable through a Codex marketplace source, similar in spirit to:

`codex plugin marketplace add owner/repo`

and then installable from the plugin browser or marketplace entry.

Because MCP is explicitly out of scope, the plugin should rely on skills plus local commands/scripts rather than exposing a Telegram MCP server.

Claude compatibility should be handled as a companion integration over the same local CLI/core package, not by assuming Codex and Claude have identical plugin marketplace mechanics.

## Non-Goals

- No MCP server in the first version.
- No multi-agent/team inbox workflow.
- No shared cloud database.
- No automatic unconfirmed Telegram posting.
- No hard-coded Mailio-specific channel, URLs, or policies.
- No attempt to reuse an already logged-in Telegram desktop/mobile session.
- No full helpdesk ticketing system in the first version.

## Open Questions For Planning

- Which Telegram client library is the best fit for local login and reply posting?
- What is the minimum setup config: chat identifier, website/blog seeds, history window, and crawl scope?
- Should the local CLI be written in Python for ML/retrieval ergonomics or TypeScript for npm/plugin distribution ergonomics?
- Which embedding model should be the default at implementation time, and how should model migrations work?
- How should the tool represent Telegram reply chains and linked discussion comments?
- What is the Claude-specific packaging surface that gives the closest user experience to the Codex plugin?

## Success Criteria

- A new user can install the plugin, configure one Telegram chat and website/blog seed, log in once, and index data without manual file editing for the happy path.
- The operator can ask for a reply to a Telegram user/message and receive a source-grounded draft.
- The tool posts only after explicit confirmation.
- The operator can ask common analytics questions over recent Telegram history and get useful answers with supporting evidence.
- The same local data/core can be used from Codex and Claude-oriented workflows.
