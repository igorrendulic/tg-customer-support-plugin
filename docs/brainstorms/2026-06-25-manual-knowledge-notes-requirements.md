---
title: "Manual Knowledge Notes Requirements"
date: 2026-06-25
topic: manual-knowledge-notes
---

# Manual Knowledge Notes Requirements

## Summary

Add an agent-led way for a Support Operator to save durable Manual Knowledge Notes into the local corpus. Notes represent dated support facts, policy changes, and operational caveats that can override or reinterpret older Telegram and web evidence after operator confirmation.

---

## Problem Frame

Some support truth changes outside Telegram history and public documentation. For example, an account-transfer policy can be discontinued on April 2, 2026, while older Telegram answers and crawled pages still describe the previous behavior.

Without a manual knowledge layer, the Agent Surface may retrieve older evidence and produce a draft that is historically accurate but operationally wrong. The operator needs a way to save current support truth locally, attach validity windows, and make conflicts visible before those notes change an answer.

---

## Key Decisions

- **Natural-language capture is primary.** The Support Operator should be able to tell Codex to save a note, while the Local Core owns the persisted record and retrieval behavior.
- **Confirmed save is required.** Codex must show the extracted note fields and wait for operator confirmation before changing the local corpus.
- **Manual notes are validity-scoped.** Each note supports an effective window and an optional expiry window so outdated notes stop influencing answers.
- **Active manual notes can supersede older evidence.** Manual Knowledge Notes are allowed to change how Telegram and web evidence should be interpreted, but conflicts must be visible before the agent relies on them.
- **Conflict checks re-query before resolution.** When a note appears to conflict with prior corpus evidence, the system should search fresher indexed Telegram and web evidence before asking the operator how to proceed.

---

## Actors

- A1. **Support Operator:** The local human who supplies the note, reviews parsed fields, confirms saves, and resolves conflicts before drafts use contested knowledge.
- A2. **Agent Surface:** Codex workflow that extracts candidate notes from natural language, presents confirmation prompts, and shows note-based evidence during answering or drafting.
- A3. **Local Core:** The shared CLI and Python core that persists notes, indexes them, evaluates validity windows, performs retrieval, and reports conflicts.
- A4. **Existing Corpus:** The locally indexed Telegram history and crawled web resources that may support, predate, or conflict with manual notes.

---

## Requirements

**Note Capture**

- R1. The Agent Surface must support a natural-language request to save a Manual Knowledge Note.
- R2. The Agent Surface must extract the note body, effective date, optional expiry date, and any caveats or context needed to make the note usable later.
- R3. The Agent Surface must show the parsed fields and require operator confirmation before the Local Core saves the note.
- R4. The save flow must allow the operator to revise or cancel the candidate note before it changes the corpus.

**Validity and Retrieval**

- R5. Each Manual Knowledge Note must have an effective date or equivalent validity start.
- R6. Each Manual Knowledge Note must support an optional expiry date or equivalent validity end.
- R7. Retrieval must treat active Manual Knowledge Notes as higher-priority evidence than older Telegram or web sources when the note applies to the question or draft.
- R8. Expired or not-yet-effective notes must not silently influence drafts or analytics answers as current support truth.
- R9. When a Manual Knowledge Note influences an answer or draft, it must appear in the Evidence Bundle shown to the operator.

**Conflict Handling**

- R10. The system must detect likely conflicts between an applicable Manual Knowledge Note and retrieved Telegram or web evidence.
- R11. When a likely conflict is detected, the system must re-query fresher indexed corpus evidence before asking the operator to resolve the conflict.
- R12. The Agent Surface must flag unresolved conflicts and ask the operator before treating the Manual Knowledge Note as settled truth for the answer or draft.
- R13. The conflict prompt must show enough note and evidence context for the operator to decide which source should guide the response.

**Workflow Integration**

- R14. Manual Knowledge Notes must participate in normal search, draft-context, and evidence-backed support workflows.
- R15. Manual Knowledge Notes must preserve the local-first profile boundary and remain stored with the operator-owned Support Profile.
- R16. The Codex skill must explain when it is saving a note, when it is using a note as evidence, and when a conflict blocks an answer or draft.

---

## Key Flows

- F1. Save a dated policy note
  - **Trigger:** The operator tells Codex to save a new support fact or policy change.
  - **Actors:** A1, A2, A3
  - **Steps:** Codex extracts the candidate note, validity window, and caveats; Codex shows the parsed fields; the operator confirms or revises; the Local Core saves the confirmed note.
  - **Outcome:** The note becomes a local corpus source only after confirmation.
  - **Covered by:** R1, R2, R3, R4, R5, R6, R15

- F2. Use an active note in a draft
  - **Trigger:** The operator asks for a draft where an active Manual Knowledge Note applies.
  - **Actors:** A1, A2, A3, A4
  - **Steps:** Retrieval includes the active note, ranks it above older evidence, and returns it in the Evidence Bundle.
  - **Outcome:** The operator can see that the draft relies on the manual note before posting.
  - **Covered by:** R7, R8, R9, R14, R16

- F3. Resolve a conflicting answer
  - **Trigger:** An active Manual Knowledge Note conflicts with Telegram or web evidence retrieved for a draft or answer.
  - **Actors:** A1, A2, A3, A4
  - **Steps:** The Local Core re-queries fresher indexed evidence, the Agent Surface shows the conflict, and the operator chooses how to proceed.
  - **Outcome:** The agent does not silently resolve contested support truth.
  - **Covered by:** R10, R11, R12, R13, R16

---

## Scope Boundaries

### In Scope

- Agent-led natural-language capture for durable support notes.
- Confirmation before saving a Manual Knowledge Note.
- Effective and optional expiry windows.
- Manual note evidence in search, drafting, and support-answer workflows.
- Conflict detection, fresher-evidence re-query, and operator resolution prompts.

### Deferred for Later

- Periodic stale-note audits.
- Review queues for old or soon-expiring notes.
- Bulk import of manual knowledge.
- Collaborative editing or multi-operator ownership.

### Outside This Product's Identity

- Silent corpus mutation from casual conversation.
- Silent conflict resolution when manual notes contradict other evidence.
- Hosted knowledge-base management.

---

## Dependencies / Assumptions

- The Local Core remains the source of truth for persistence, indexing, retrieval, and evidence formatting.
- Support Profiles continue to hold local corpus state outside the plugin source tree.
- Exact conflict-detection and keyword-replanning mechanics are implementation-planning decisions.
- The indexed Telegram and web corpus may not contain enough fresher evidence to resolve every conflict automatically.

---

## Acceptance Examples

- AE1. **Covers R1, R2, R3, R4.** Given the operator says an account-transfer policy was discontinued on April 2, 2026, when Codex extracts a Manual Knowledge Note, then Codex shows the note text and effective date before saving.
- AE2. **Covers R5, R6, R8.** Given a note has an expiry date, when a later draft request falls outside the note window, then the note does not influence the draft as current truth.
- AE3. **Covers R7, R9, R14.** Given an active note applies to a user's question, when retrieval prepares draft context, then the note appears in the Evidence Bundle and is ranked above older conflicting sources.
- AE4. **Covers R10, R11, R12, R13.** Given an active note conflicts with older web or Telegram evidence, when the agent prepares an answer, then it re-queries fresher indexed evidence and asks the operator before applying the note as settled truth.
- AE5. **Covers R15, R16.** Given a note is saved through Codex, when the workflow completes, then the note is stored in the local Support Profile and the Agent Surface reports what changed.

---

## Success Criteria

- The operator can save a dated support policy note through Codex without manually editing files.
- Saved notes do not affect retrieval until the operator confirms the parsed fields.
- Active manual notes can correct drafts that would otherwise rely on stale Telegram or web evidence.
- Evidence shown for a draft makes manual-note influence visible.
- Conflicts between manual notes and other corpus sources are surfaced rather than silently resolved.

---

## Sources / Research

- `README.md` describes the current local-first corpus as Telegram history plus crawled website or blog resources.
- `CONCEPTS.md` defines Support Operator, Agent Surface, Local Core, Support Profile, and Evidence Bundle.
- `skills/telegram-support/SKILL.md` requires CLI JSON to be the source of truth for corpus state and evidence.
- `tg_support/cli.py` currently exposes setup, sync, crawl, index, search, stats, draft, and confirmation commands.
- `tg_support/storage/schema.py` currently constrains retrievable chunks to Telegram and web sources.
- `tg_support/indexing/chunking.py` currently chunks web pages and Telegram conversation windows.
- `docs/solutions/architecture-patterns/thin-agent-surfaces-shared-local-cli-core.md` states that new support behavior should land in the Local Core first and be exposed through the CLI before agent surfaces reference it.
