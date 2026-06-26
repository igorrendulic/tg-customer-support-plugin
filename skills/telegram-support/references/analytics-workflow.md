# Analytics Workflow

Run `status` first. If the profile is not ready, follow the setup preflight in `../SKILL.md` instead of answering from an incomplete corpus.

Use structured stats commands for direct counts:

```bash
scripts/tg-support stats message-count --since 2026-01-01
scripts/tg-support stats active-users
scripts/tg-support stats replied-to-users
scripts/tg-support stats links
```

Use `search` for evidence-heavy questions such as repeated complaints, common workarounds, release reactions, or recurring resource links:

```bash
scripts/tg-support search "password reset complaints"
```

Exact Telegram author usernames can also be searched through normal `search`; use the returned Telegram evidence rather than treating a username match as a standalone user record.

For analytics questions that turn into product-behavior or debugging claims, run `repo-evidence` for the behavior claim and cite Repository Evidence ahead of Manual Knowledge Notes, Telegram evidence, and web evidence. Do not run repository lookup for normal volume, activity, or theme analytics.

If `search` returns non-empty `conflicts`, show the Manual Knowledge Note, older evidence, and fresher evidence to the operator before answering. Ask which source should guide the answer when the conflict changes the conclusion.

When answering, separate computed counts from inferred themes. Cite the returned chunk IDs and source metadata. If the corpus is small or evidence is weak, say that rather than inventing clusters.
