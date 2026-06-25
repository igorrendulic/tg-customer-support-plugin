---
title: "GitHub Repo Evidence Requirements"
date: 2026-06-25
topic: github-repo-evidence
---

# GitHub Repo Evidence Requirements

## Summary

Add a read-only GitHub repository evidence source for product-behavior and debugging support questions. The Agent Surface should manage a local checkout for a configured GitHub repository and branch, refresh it when stale, and cite branch-specific code as the highest-priority evidence.

---

## Problem Frame

Some support answers depend on what the product code does now, not what the operator remembers or what public docs say. The Support Operator currently relies on memory, web browsing, and targeted code reading that often starts at APIs before tracing through implementation details.

That works for expert debugging, but it makes agent-assisted answers vulnerable to stale assumptions. When a user asks why a capability works, does not work, or fails in a particular case, the support workflow needs a way to ground the answer in the configured production branch before falling back to lower-priority evidence.

---

## Key Decisions

- **Repository evidence is live, not indexed.** The repository changes too often for stored chunks to remain trustworthy, so repo lookup reads a managed checkout on demand.
- **Configured branch code is the top source of truth.** Code from the configured production branch outranks Manual Knowledge Notes, and Manual Knowledge Notes outrank Telegram and web evidence.
- **Repo lookup is conditional.** The Agent Surface should check code only for product-behavior, capability, or debugging questions instead of every support request.
- **Stale code is allowed only with a warning.** If the checkout is stale and refresh fails, the Agent Surface can still answer from the stale checkout, but it must make that limitation visible.

---

## Actors

- A1. **Support Operator:** The local human who configures the repository and reviews code-grounded support answers.
- A2. **Agent Surface:** Codex or another wrapper that decides when a support question needs repository evidence and presents citations or freshness warnings.
- A3. **Local Core:** The shared CLI and Python core that manages profile-local repository checkout state and exposes source-linked evidence to agent surfaces.
- A4. **GitHub Repository:** The configured upstream repository and branch used as the authoritative code source for product behavior.
- A5. **Existing Corpus:** Telegram history, crawled web resources, and Manual Knowledge Notes used when repository evidence is unavailable or not relevant.

---

## Requirements

**Repository Configuration**

- R1. The Support Profile must support a configured GitHub repository and branch for repository evidence.
- R2. Repository setup must rely on the operator's existing local `gh` or `git` authentication rather than asking the operator to provide new GitHub credentials.
- R3. Repository checkout state must remain profile-local and separate from the plugin source repository.
- R4. Repository evidence access must be read-only from the support workflow.

**Freshness and Checkout Management**

- R5. Before using repository evidence, the Local Core must check whether the managed checkout is stale against the configured branch.
- R6. If the checkout is stale, the Local Core must refresh it before reading files when refresh succeeds.
- R7. If the checkout is stale and refresh fails, the Agent Surface must warn the operator and mark repository evidence as stale when answering.
- R8. A stale-check failure must not silently demote code evidence below lower-priority sources.

**Retrieval and Evidence Priority**

- R9. The Agent Surface must request repository evidence only when the question concerns product behavior, supported capabilities, API behavior, or debugging symptoms.
- R10. Repository evidence from the configured branch must outrank Manual Knowledge Notes, Telegram evidence, and web evidence when sources disagree.
- R11. Repository evidence must include source references precise enough for the operator to inspect the cited code.
- R12. When repository evidence is not relevant, unavailable, or insufficient, the support workflow must continue to use Manual Knowledge Notes, Telegram evidence, and web evidence.

**Answer Behavior**

- R13. Code-grounded answers must explain the answer in support language rather than dumping raw code.
- R14. If repository evidence changes the answer implied by lower-priority sources, the Agent Surface must show that the code evidence is taking precedence.
- R15. The Agent Surface must not write Manual Knowledge Notes automatically from code findings.
- R16. The support workflow must not modify the configured GitHub repository or create pull requests as part of answering support questions.

---

## Key Flows

- F1. Configure repository evidence
  - **Trigger:** The operator configures a Support Profile with a GitHub repository and branch.
  - **Actors:** A1, A3, A4
  - **Steps:** The Local Core records the repo and branch, prepares a profile-local managed checkout, and relies on existing local GitHub authentication.
  - **Outcome:** The Support Profile can use branch-specific code evidence without storing new GitHub credentials.
  - **Covered by:** R1, R2, R3, R4

- F2. Answer a product-behavior question
  - **Trigger:** The operator asks why a feature is supported, unsupported, or behaving a certain way.
  - **Actors:** A1, A2, A3, A4, A5
  - **Steps:** The Agent Surface identifies the question as code-relevant, the Local Core checks checkout freshness, refreshes if needed, and the Agent Surface reads targeted code evidence before composing the answer.
  - **Outcome:** The answer is grounded in the configured branch and cites the relevant code evidence.
  - **Covered by:** R5, R6, R9, R10, R11, R13, R14

- F3. Answer when refresh fails
  - **Trigger:** A code-relevant question needs repository evidence, but the managed checkout is stale and cannot refresh.
  - **Actors:** A1, A2, A3, A4, A5
  - **Steps:** The Local Core reports the failed refresh, the Agent Surface warns that repo evidence is stale, and the answer uses the stale checkout plus any lower-priority evidence.
  - **Outcome:** Support can continue, but the operator sees that the code evidence may be outdated.
  - **Covered by:** R5, R7, R8, R12, R13

---

## Scope Boundaries

### In Scope

- Configuring a GitHub repository and branch as a read-only evidence source.
- Managing a profile-local checkout for support-time code reading.
- Checking freshness before repository evidence is used.
- Refreshing stale checkouts when possible.
- Warning when stale repository evidence is used.
- Prioritizing configured-branch code above Manual Knowledge Notes, Telegram evidence, and web evidence.

### Deferred for Later

- Indexing repository contents into the normal retrieval store.
- Repository change summaries or release-diff analysis.
- Operator controls for multiple repositories or branch precedence rules.
- Manual Knowledge Note suggestions generated from code findings.

### Outside This Product's Identity

- Asking operators to paste GitHub credentials into the support workflow.
- Modifying product code, creating branches, or opening pull requests from support answers.
- Treating web docs or Telegram history as higher authority than configured production-branch code for behavior questions.

---

## Dependencies / Assumptions

- The operator already has local `gh` or `git` authentication capable of reading the configured repository.
- The configured branch is the support authority for product behavior, with the production branch as the expected common case.
- Repository evidence can be gathered through targeted code search and file reads rather than full indexing.
- The Local Core remains responsible for profile-local state, while Agent Surfaces remain thin wrappers around shared behavior.
- Some behavior questions will still require operator judgment when code, docs, and historical support answers point in different directions.

---

## Acceptance Examples

- AE1. **Covers R1, R2, R3, R4.** Given the operator configures a GitHub repo and production branch, when repository evidence setup runs, then the checkout is profile-local, read-only to the support workflow, and uses existing local GitHub authentication.
- AE2. **Covers R5, R6, R9, R11.** Given a product-behavior question is asked and the checkout is stale, when refresh succeeds, then the answer uses refreshed branch evidence with code references.
- AE3. **Covers R7, R8, R12.** Given a product-behavior question is asked and refresh fails, when the Agent Surface answers from the stale checkout, then it warns that repository evidence may be outdated.
- AE4. **Covers R10, R14.** Given production-branch code disagrees with a Manual Knowledge Note or public documentation, when the Agent Surface answers a behavior question, then it treats the code as the higher-priority source and shows that precedence.
- AE5. **Covers R15, R16.** Given code reading reveals a support-relevant behavior, when the support workflow completes, then it does not write a Manual Knowledge Note or modify the repository without a separate explicit workflow.

---

## Success Criteria

- The operator can configure a GitHub repo and branch once per Support Profile.
- Code-relevant support questions get branch-grounded answers without the operator manually opening the repo.
- Repository evidence is fresh when refresh works and visibly stale when refresh fails.
- Answers cite code precisely enough for the operator to inspect the source.
- Normal support questions are not slowed down by unnecessary repo lookup.
- The support workflow preserves the local-first, read-only boundary for GitHub access.

---

## Sources / Research

- `CONCEPTS.md` defines Support Operator, Agent Surface, Local Core, Support Profile, Evidence Bundle, Manual Knowledge Note, and Conflict Check.
- `docs/brainstorms/2026-06-25-manual-knowledge-notes-requirements.md` defines Manual Knowledge Notes as local support truth that can override older Telegram and web evidence.
- `docs/brainstorms/telegram-support-agent-requirements.md` defines the local-first support agent, Evidence Bundle expectations, and the Telegram/web corpus.
- `tg_support/indexing/hybrid.py` currently boosts Manual Knowledge Notes over other indexed sources and reports conflicts.
- `tg_support/storage/schema.py` currently stores retrievable chunks for Telegram, web, and manual sources.
- `tg_support/cli.py` exposes shared Local Core commands through the agent-facing CLI.
