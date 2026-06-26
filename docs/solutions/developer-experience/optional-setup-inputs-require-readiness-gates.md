---
title: "Optional setup inputs require matching readiness gates"
date: 2026-06-26
category: developer-experience
module: telegram-support-agent
problem_type: developer_experience
component: development_workflow
severity: medium
applies_when:
  - "Making setup inputs optional for a local agent profile"
  - "Changing CLI defaults that are also described by agent-facing setup instructions"
  - "Keeping status preflight output aligned with optional profile capabilities"
related_components:
  - assistant
  - tooling
tags:
  - setup
  - readiness
  - optional-inputs
  - agent-surfaces
  - defaults
---

# Optional setup inputs require matching readiness gates

## Context

The setup flow originally required a Telegram chat and at least one website or blog seed URL. When seed URLs became optional, the first-order change was simple: allow `setup --chat support` to write a valid profile. The durable lesson is broader: optional setup inputs must also change status readiness, stored configuration shape, CLI defaults, tests, and every thin agent surface that tells an operator what setup requires.

The same pass changed the optional GitHub repository branch default from `production` to `main`. That default lived in both `tg_support.config.normalize_branch` and the setup parser, while product docs and skills still taught operators to think in production-branch terms.

## Guidance

Treat setup optionality as a contract across three layers:

- The config parser must accept the absent value and persist a stable empty shape.
- The readiness preflight must skip downstream work that only exists when the optional input is configured.
- Agent-facing setup copy must stop asking for optional values as if they are required.

For seed URLs, this meant removing the empty-seed validation and normalizing missing CLI seeds to an empty list:

```python
seeds_data = data.get("seeds") or []
seeds: list[SeedConfig] = []
for item in seeds_data:
    ...
```

```python
"seeds": [{"url": seed, "render": args.render} for seed in args.seed or []],
```

The key readiness change was not in setup. A profile with no seeds has nothing to crawl, so `status` must not keep returning `next_action: "crawl"` after Telegram history is synced:

```python
pages = usable_page_count(db) if database_ok else 0
web_crawl_ready = not config.seeds or pages > 0
...
"web_crawl": web_crawl_ready,
```

For repository branches, keep the default in the shared config helper and mirror it at the CLI argument boundary:

```python
def normalize_branch(value: str | None) -> str:
    branch = (value or "main").strip()
```

```python
setup.add_argument("--repository-branch", default="main")
```

When changing a setup default, search docs, skills, and agent descriptors for stale examples. In this repo that included `README.md`, `docs/setup.md`, `skills/telegram-support/SKILL.md`, `agents/claude.md`, and `agents/openai.yaml`.

## Why This Matters

Agent setup flows are driven by readiness JSON and prose instructions. If config accepts an optional value but status still expects downstream artifacts from that value, the operator gets stuck in a false setup loop. If the CLI default changes but skill text still teaches the old default, each agent surface reintroduces the old product behavior by habit.

The local CLI is the shared source of product behavior, but the thin agent surfaces shape what operators provide. Defaults and optional inputs therefore need regression coverage at both the core CLI layer and the operator-guidance layer.

## When to Apply

- Making a profile input optional.
- Adding optional evidence sources, crawlers, repositories, credentials, adapters, or indexes.
- Changing a setup default that appears in CLI examples or agent instructions.
- Adding a new readiness check that should be conditional on profile configuration.

## Examples

Good coverage for this change included:

```python
def test_cli_setup_allows_no_seed(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    code = main(["setup", "--chat", "support"])
    assert code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    config = load_config(tmp_path / "default" / "config.json")
    assert config.seeds == ()
```

```python
def test_status_skips_crawl_when_no_seeds_configured(tmp_path, capsys, monkeypatch):
    ...
    assert main(["status"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["checks"]["web_crawl"] is True
    assert output["next_action"] == "index"
```

```python
def test_cli_setup_repository_branch_defaults_to_main(tmp_path, capsys, monkeypatch):
    ...
    config = load_config(tmp_path / "default" / "config.json")
    assert config.repository is not None
    assert config.repository.branch == "main"
```

The anti-pattern is accepting `setup --chat support` while leaving status to require crawled pages. That stores a valid profile but makes readiness impossible without adding a seed later.

## Related

- `docs/solutions/architecture-patterns/thin-agent-surfaces-shared-local-cli-core.md` describes why setup behavior belongs in the shared CLI/core while skills and agent descriptors remain thin surfaces.
- `tg_support/config.py` owns profile config normalization and branch defaults.
- `tg_support/cli.py` owns setup argument mapping and readiness preflight output.
- `tests/test_config.py` and `tests/test_cli_setup.py` are the regression anchors for setup optionality and readiness state.
