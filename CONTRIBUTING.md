# Contributing

Thanks for improving Telegram Support Agent. This project is intentionally local-first: keep support data on the operator's machine, keep Codex and Claude surfaces thin, and put durable behavior in the shared Python CLI/core.

## Development

Create a virtual environment and install development dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Install optional extras only when your change needs them:

```bash
.venv/bin/pip install -e ".[telegram,render,dev]"
.venv/bin/playwright install
```

Run tests before sending a change:

```bash
.venv/bin/pytest
```

## Project Boundaries

- Put runtime behavior in `tg_support/` and expose it through `tg_support.cli`.
- Keep `skills/` and `agents/` as thin workflow/instruction surfaces over the CLI.
- Keep Telegram writes behind persisted drafts and explicit confirmation tokens.
- Store operator data in local profiles, not in the source tree.
- Preserve source references from Telegram messages and crawled pages through retrieval results.

## Documentation

Update docs with behavior changes:

- `README.md` for user-facing setup and common workflows.
- `docs/setup.md` for local profile, optional dependency, and indexing details.
- `docs/claude-usage.md` and `agents/claude.md` for Claude-specific guidance.
- `skills/telegram-support/` for Codex workflow changes.
- `docs/solutions/` for durable lessons that future agents should search before changing related areas.
- `CONCEPTS.md` for project-specific vocabulary.

## Tests

Add or update focused tests for changed behavior. The confirmation flow is especially important:

- cancellation must never send a Telegram message;
- post tokens must send at most once;
- missing reply targets must fail rather than silently posting a normal message;
- infrastructure failures must not burn a usable confirmation token before a send is possible.

Use fakes at adapter boundaries where possible. Real Telegram, Playwright, and embedding/vector integrations should stay optional so the core suite remains fast and local.
