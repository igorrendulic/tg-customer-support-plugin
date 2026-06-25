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

## Install For Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Configure

```bash
scripts/tg-support --profile default setup --chat my-support-chat --seed https://example.com/blog
```

Chat inputs such as `channel-name`, `@channel-name`, and `https://t.me/channel-name` normalize to the same configured chat.

Seed render modes:

- `auto`: fetch static HTML first and render JavaScript app-shell pages.
- `always`: use Playwright rendering.
- `never`: do not render; empty app shells are reported without browser work.

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

## Reset

Remove the profile directory for the profile you want to reset:

```bash
rm -rf ~/.tg-support/profiles/default
```

Do this only when you intend to delete the local config, Telegram API credentials, Telegram session, SQLite database, and indexes for that profile.
