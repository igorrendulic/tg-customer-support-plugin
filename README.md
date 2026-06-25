# Telegram Support Agent

Telegram Support Agent is a local-first Codex plugin and Python CLI for a single support operator who answers questions in a Telegram support chat. It indexes a configured Telegram chat plus website or blog resources, answers support analytics questions, prepares evidence-backed reply drafts, and posts to Telegram only after explicit operator confirmation.

It is for founders, maintainers, and support engineers who already handle support in Telegram and want searchable local context without moving support data into a hosted helpdesk. The agent surfaces stay thin: Codex and Claude workflows call the same local CLI, while Telegram sessions, SQLite metadata, retrieval indexes, drafts, and confirmation records stay on the operator's machine.

## Install

For Codex, add the plugin marketplace and install the plugin:

```bash
codex plugin marketplace add igorrendulic/tg-customer-support-plugin
codex plugin add telegram-support-agent@tg-customer-support-plugin
```

That installs the Codex workflow. The first time the workflow runs the bundled `scripts/tg-support` helper, it creates its own runtime environment, installs the Telegram and browser-rendering dependencies, and installs Chromium for Playwright.

To run the CLI directly outside Codex:

```bash
git clone https://github.com/igorrendulic/tg-customer-support-plugin.git
cd tg-customer-support-plugin
scripts/tg-support --help
```

By default, the auto-created environment lives under `~/.local/share/tg-support/runtime/.venv`. Set `TG_SUPPORT_VENV` to put it somewhere else.

The package also exposes a `tg-support` console script inside that auto-created environment:

```bash
~/.local/share/tg-support/runtime/.venv/bin/tg-support --help
```

### Development Install

For local development, clone the repo and install the package with dev dependencies:

```bash
git clone <repo-url>
cd tg-support-plugin
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Add optional adapters when you need them:

```bash
.venv/bin/pip install -e ".[telegram,render,dev]"
```

## Use

Create a local profile with one Telegram chat and at least one website or blog seed:

```bash
scripts/tg-support --profile default setup \
  --chat my-support-chat \
  --seed https://example.com/blog
```

Then build the local corpus:

```bash
scripts/tg-support --profile default login
scripts/tg-support --profile default sync
scripts/tg-support --profile default crawl
scripts/tg-support --profile default index
```

Ask questions or prepare a reply draft:

```bash
scripts/tg-support --profile default search "password reset issues"
scripts/tg-support --profile default stats active-users
scripts/tg-support --profile default draft-context --user alice
scripts/tg-support --profile default draft-create --message-id 123 --text "Thanks, try the reset link here..."
```

Posting is intentionally a separate confirmed action. Show the operator the exact draft, target, and evidence first, then use the generated post or cancel token:

```bash
scripts/tg-support --profile default confirm <post_or_cancel_token>
```

Local profile data lives outside the source tree by default:

```text
~/.local/share/tg-support/profiles/<profile>/
```

Set `TG_SUPPORT_HOME` to move profile data elsewhere.

## Codex And Claude

The Codex skill lives in `skills/telegram-support/`. It uses the same `scripts/tg-support` commands as the CLI examples above and treats JSON CLI output as the source of truth for evidence, draft IDs, and confirmation tokens.

Claude companion guidance is in `agents/claude.md` and `docs/claude-usage.md`. Claude should use the same local CLI and must not post directly or infer confirmation from casual approval.

## Why This Shape

The project follows the same practical README shape as tools like CLI Printing Press: start with what the tool is, install both the agent-facing surface and the binary/core, show the workflow, then explain the non-obvious architecture. Here, the non-obvious part is the safety boundary: agent prompts can retrieve evidence and draft text, but only deterministic CLI code can consume a confirmation token and write to Telegram.

SQLite is the durable local metadata store. Lexical and vector indexes are rebuildable projections linked back to Telegram messages and crawled pages, so answers can cite source records instead of relying on agent memory.

## Development

Install dev dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Run the test suite:

```bash
.venv/bin/pytest
```

Useful project files:

- `tg_support/cli.py` defines the command boundary.
- `tg_support/storage/schema.py` defines the local SQLite shape.
- `tg_support/support/drafting.py` and `tg_support/support/posting.py` own the draft and confirmation flow.
- `skills/telegram-support/SKILL.md` defines the Codex operator workflow.
- `docs/solutions/` captures durable architecture and workflow learnings.
- `CONCEPTS.md` defines project vocabulary.

See `CONTRIBUTING.md` for contribution guidelines.
