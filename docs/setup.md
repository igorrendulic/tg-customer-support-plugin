# Telegram Support Agent Setup

This package is local-first. Telegram sessions, SQLite data, and indexes live under:

```text
~/.tg-support/profiles/<profile>/
```

The source tree should not contain profile data. The `scripts/tg-support` helper also bootstraps its own Python runtime outside the source tree by default:

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
scripts/tg-support setup --profile default --chat my-support-chat --seed https://example.com/blog
```

Chat inputs such as `channel-name`, `@channel-name`, and `https://t.me/channel-name` normalize to the same configured chat.

Seed render modes:

- `auto`: fetch static HTML first and render JavaScript app-shell pages.
- `always`: use Playwright rendering.
- `never`: do not render; empty app shells are reported without browser work.

## Indexing Flow

```bash
scripts/tg-support login
scripts/tg-support sync
scripts/tg-support crawl
scripts/tg-support index
```

The first version exposes Telethon and Playwright through the helper-managed runtime. Tests use fakes; real Telegram access still requires local Telegram API credentials.

## Reset

Remove the profile directory for the profile you want to reset:

```bash
rm -rf ~/.tg-support/profiles/default
```

Do this only when you intend to delete the local Telegram session, SQLite database, and indexes for that profile.
