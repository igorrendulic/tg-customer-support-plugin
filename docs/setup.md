# Telegram Support Agent Setup

This package is local-first. Telegram sessions, SQLite data, and indexes live under:

```text
~/.tg-support/profiles/<profile>/
```

The source tree should not contain profile data. A profile can contain config, Telegram API credentials, a Telegram session file, SQLite data, and rebuildable indexes. Treat the profile directory as sensitive local state.

The `scripts/tg-support` helper also bootstraps its own Python runtime outside the source tree by default:

```text
~/.tg-support/.venv
```

Set `TG_SUPPORT_VENV` to use a different runtime environment.

The helper installs retrieval dependencies for normal operator use. Retrieval uses SQLite FTS5, sqlite-vec, and local `BAAI/bge-small-en-v1.5` embeddings. If your local Python or SQLite build cannot load sqlite-vec, `index` returns a JSON error with the SQLite version and the next setup action instead of falling back to hash vectors.

## Install For Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[retrieval,dev]"
```

## Configure

```bash
scripts/tg-support --profile default setup --chat my-support-chat
```

Chat inputs such as `channel-name`, `@channel-name`, and `https://t.me/channel-name` normalize to the same configured chat.

Website or blog seed URLs are optional. Add one or more when you want public support resources included in the local index:

```bash
scripts/tg-support --profile default setup \
  --chat my-support-chat \
  --seed https://example.com/blog
```

Repository Evidence is optional. Add a GitHub repository and branch when you want behavior or debugging answers grounded in code. The branch defaults to `main` when omitted:

```bash
scripts/tg-support --profile default setup \
  --chat my-support-chat \
  --repository owner/project
```

Repository setup uses your existing local `git` or `gh` authentication. The support workflow does not ask for GitHub credentials and does not modify the configured repository.

Seed render modes:

- `auto`: fetch static HTML first and render JavaScript app-shell pages.
- `always`: use Playwright rendering.
- `never`: do not render; empty app shells are reported without browser work.

`crawl` follows same-scope links two levels deep by default. Use `--depth 0` to crawl only configured seed URLs, or pass another non-negative depth for a broader bounded crawl.

## Telegram API Credentials

Real Telegram access uses Telethon and requires a Telegram API ID and API hash:

1. Log in at `https://my.telegram.org`.
2. Open API development tools.
3. Create an application if you do not already have one.
4. Copy the API ID and API hash.

Store them in the local profile:

```bash
scripts/tg-support --profile default credentials --api-id 123456
```

The API hash is secret. The CLI reads it from an interactive hidden prompt, or from stdin with `--api-hash-stdin` for agent/tool orchestration. Do not put the literal hash in the command string. The CLI stores it under the local profile with owner-only permissions where supported and does not print it in normal JSON output.

## Indexing Flow

```bash
scripts/tg-support --profile default status
scripts/tg-support --profile default login
scripts/tg-support --profile default sync
scripts/tg-support --profile default crawl
scripts/tg-support --profile default index
scripts/tg-support --profile default status
```

The first version exposes Telethon and Playwright through the helper-managed runtime. Tests use fakes; real Telegram access still requires local Telegram API credentials.

Indexing chunks Telegram history, crawled pages, and Manual Knowledge Notes into source-linked documents, then rebuilds FTS5 and sqlite-vec projections. The index is safe to rebuild; source records, drafts, confirmations, and post attempts remain durable profile data.

## Repository Evidence

Use Repository Evidence for product-behavior, capability, API-behavior, or debugging questions:

```bash
scripts/tg-support --profile default repo-evidence "account transfer api"
```

The command manages a profile-local checkout of the configured branch and checks whether it is stale before reading code. If refresh fails, the JSON output includes a warning and may still include evidence from the last checkout. Agents should show that warning before relying on the code.

Repository Evidence is live and branch-aware. It is not stored in the normal search index, because support answers about current product behavior should read the configured branch directly.

## Manual Knowledge

Manual Knowledge Notes are profile-local support facts, policy changes, or operational caveats that should influence future answers. Prefer saving them through Codex: Codex should parse the note text, effective date, optional expiry date, and caveats, then show those fields for operator confirmation before it runs the local save command.

Direct CLI save is available for confirmed fields:

```bash
scripts/tg-support --profile default knowledge-add \
  --text "Account transfers were discontinued. Users must register a new email address." \
  --effective-date 2026-04-02 \
  --caveats "Old email addresses are quarantined until further notice."
scripts/tg-support --profile default index
```

Use `--expires-date YYYY-MM-DD` when the note should stop applying after a known date. Active notes can outrank older Telegram or web evidence. When search or draft context returns `conflicts`, the agent should show the note, older evidence, and fresher evidence to the operator before using the note as settled truth.

## Reset

Remove the profile directory for the profile you want to reset:

```bash
rm -rf ~/.tg-support/profiles/default
```

Do this only when you intend to delete the local config, optional repository checkout state, Telegram API credentials, Telegram session, SQLite database, and indexes for that profile.
