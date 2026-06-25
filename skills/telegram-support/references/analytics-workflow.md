# Analytics Workflow

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

When answering, separate computed counts from inferred themes. Cite the returned chunk IDs and source metadata. If the corpus is small or evidence is weak, say that rather than inventing clusters.
