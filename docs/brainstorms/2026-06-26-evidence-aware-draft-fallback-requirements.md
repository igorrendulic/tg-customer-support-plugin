---
title: "Evidence-Aware Draft Fallback Requirements"
date: 2026-06-26
topic: evidence-aware-draft-fallback
---

# Evidence-Aware Draft Fallback Requirements

## Summary

Evidence-aware reply drafting should first try to produce a direct support answer from collected evidence. When evidence is missing, weak, conflicting, stale, vague, or account-specific information is needed, the Agent Surface should present two draft options: a cautious evidence-limited answer and a DM follow-up asking the user for the missing information.

---

## Problem Frame

Manual Knowledge Notes are useful when the Support Operator confirms durable support truth, but not every operator instruction is truth. “Ask the user to DM me private information” is not evidence about the product, policy, or prior support history. It is a fallback reply action for situations where the corpus cannot support a direct answer.

If that kind of request is stored as knowledge, it can pollute retrieval and later appear as if it answers unrelated questions about private information, accounts, logs, billing, or email addresses. The draft workflow needs a way to keep evidence authority separate from operator-controlled follow-up options.

---

## Key Decisions

- **Evidence first.** The workflow should collect and inspect evidence before offering a DM follow-up option.
- **Fallback action is not evidence.** A DM request may shape a draft option, but it must not become source-of-truth knowledge or rank alongside evidence.
- **Two options preserve operator judgment.** Weak evidence should not force an automatic escalation or a forced direct answer.
- **Sufficiency is a workflow concept.** The system needs to distinguish answerable evidence bundles from evidence bundles that require operator choice.

---

## Actors

- A1. **Support Operator:** The local human who reviews evidence, chooses which draft to send, and decides whether more user information is needed.
- A2. **Agent Surface:** Codex or another agent-facing workflow that presents evidence, drafts response options, and keeps fallback guidance separate from evidence.
- A3. **Local Core:** The shared CLI and Python core that returns evidence bundles, conflicts, warnings, and enough metadata for the Agent Surface to judge answerability.
- A4. **Support User:** The Telegram user who receives either a direct answer or a request to DM missing private or account-specific information.

---

## Requirements

**Evidence Assessment**

- R1. The Agent Surface must collect relevant evidence before deciding whether to draft a direct answer or offer a DM follow-up option.
- R2. The workflow must treat no relevant evidence, weak evidence, conflicting evidence, stale evidence, vague evidence, and account-specific gaps as insufficient for an unqualified direct answer.
- R3. Evidence insufficiency must be visible to the Support Operator before they choose a draft option.
- R4. Repository Evidence, Manual Knowledge Notes, Telegram evidence, and web evidence must keep their existing source-priority semantics when assessing answerability.

**Draft Options**

- R5. When evidence supports a direct answer, the Agent Surface should draft the direct answer without adding an unnecessary DM fallback.
- R6. When evidence is insufficient, the Agent Surface must present two options: a cautious evidence-limited answer and a DM follow-up asking for the missing information.
- R7. The cautious answer must make its uncertainty or evidence limit visible in operator-facing context before posting.
- R8. The DM follow-up must ask only for the information needed to unblock the support answer.
- R9. The draft body should stay natural, while the evidence or draft summary shows that an evidence-insufficiency fallback was applied.

**Truth Boundary**

- R10. A DM follow-up instruction must not be saved as a Manual Knowledge Note.
- R11. A DM follow-up instruction must not appear in an Evidence Bundle as support truth.
- R12. A DM follow-up option must not resolve conflicts between Manual Knowledge Notes, Repository Evidence, Telegram evidence, or web evidence.
- R13. The workflow must preserve the existing explicit confirmation boundary before anything is posted to Telegram.

---

## Key Flows

- F1. Direct answer from sufficient evidence
  - **Trigger:** The Support Operator asks for a reply and collected evidence supports the answer.
  - **Actors:** A1, A2, A3
  - **Steps:** The Agent Surface gathers evidence, determines the evidence can support a direct answer, and drafts one reply with an evidence summary.
  - **Outcome:** The Support Operator can review and confirm a direct reply without extra fallback options.
  - **Covered by:** R1, R4, R5, R13

- F2. Two-option fallback from insufficient evidence
  - **Trigger:** The Support Operator asks for a reply and evidence is missing, weak, conflicting, stale, vague, or account-specific.
  - **Actors:** A1, A2, A3, A4
  - **Steps:** The Agent Surface shows the evidence limitation, drafts a cautious answer, and drafts a DM follow-up requesting the missing information.
  - **Outcome:** The Support Operator chooses whether to answer cautiously or ask for more information.
  - **Covered by:** R2, R3, R6, R7, R8, R9, R13

- F3. Fallback remains outside knowledge truth
  - **Trigger:** A DM follow-up option is prepared for a weak-evidence support request.
  - **Actors:** A1, A2, A3
  - **Steps:** The Agent Surface treats the DM request as a draft option only and does not save it into manual knowledge or evidence.
  - **Outcome:** Future retrieval is not polluted by fallback instructions.
  - **Covered by:** R10, R11, R12

---

## Scope Boundaries

### In Scope

- Evidence-aware answerability checks during reply drafting.
- Two draft options when evidence is insufficient.
- DM follow-up wording for missing private, account-specific, or support-blocking details.
- Operator-visible indication that a fallback option was created because evidence was insufficient.
- Preservation of existing evidence priority and posting confirmation boundaries.

### Deferred for Later

- A general saved preference manager for reply rules.
- Editable templates for different follow-up styles.
- Analytics on how often fallback options are chosen.
- Automated learning from chosen fallback drafts.

### Outside This Product's Identity

- Saving “ask them to DM me” as source-of-truth knowledge.
- Treating fallback guidance as evidence.
- Automatically escalating to DM before evidence has been collected.
- Posting either option without explicit Support Operator confirmation.

---

## Dependencies / Assumptions

- The existing Evidence Bundle remains the operator-visible evidence surface for drafts.
- Existing conflict reporting remains authoritative for contested Manual Knowledge Notes.
- Repository Evidence continues to outrank Manual Knowledge Notes, Telegram evidence, and web evidence for product-behavior or debugging questions.
- Planning will decide how the first version detects evidence insufficiency.

---

## Acceptance Examples

- AE1. **Covers R1, R5.** Given Repository Evidence or other retrieved evidence directly answers a support question, when the operator asks for a draft, then the Agent Surface drafts a direct answer and does not add a DM fallback option.
- AE2. **Covers R2, R3, R6.** Given search returns no relevant evidence, when the operator asks for a draft, then the Agent Surface shows the evidence gap and presents both a cautious answer option and a DM follow-up option.
- AE3. **Covers R2, R6, R12.** Given Manual Knowledge Notes conflict with other evidence, when the operator asks for a draft, then the Agent Surface presents a conflict-aware cautious answer and a DM follow-up option without treating the DM option as conflict resolution.
- AE4. **Covers R8, R9.** Given the answer depends on a private account email, when the DM follow-up option is drafted, then the draft asks for that missing detail by DM and the summary shows that an evidence-insufficiency fallback was applied.
- AE5. **Covers R10, R11.** Given a DM follow-up option is generated, when the workflow completes, then no Manual Knowledge Note is created and the DM wording does not appear as evidence in later retrieval.
- AE6. **Covers R13.** Given either draft option is prepared, when the operator has not confirmed posting, then no Telegram message is sent.

---

## Success Criteria

- Strong evidence produces a direct draft without unnecessary escalation.
- Insufficient evidence produces two clear operator choices instead of a single overconfident answer.
- DM follow-up wording never pollutes the knowledge base or evidence ranking.
- The operator can see why the fallback option appeared before choosing what to send.
- Existing evidence priority, conflict visibility, and posting confirmation behavior remain intact.

---

## Sources / Research

- `CONCEPTS.md` defines Evidence Bundle, Manual Knowledge Note, Repository Evidence, Conflict Check, Draft, and Confirmation Token.
- `docs/brainstorms/2026-06-25-manual-knowledge-notes-requirements.md` defines Manual Knowledge Notes as confirmed support truth that can override older evidence.
- `docs/brainstorms/2026-06-25-github-repo-evidence-requirements.md` defines Repository Evidence as the highest-priority source for product-behavior and debugging questions.
- `skills/telegram-support/SKILL.md` requires Manual Knowledge saves to be confirmed and requires conflicts to be shown before treating contested notes as settled truth.
- `skills/telegram-support/references/reply-workflow.md` defines the current evidence-backed drafting workflow and posting safety boundary.
- `tg_support/support/context.py` currently prepares draft context from user history, thread context, evidence, conflicts, and suggestions.
- `tg_support/support/knowledge.py` currently saves Manual Knowledge Notes only through the explicit manual knowledge path.
