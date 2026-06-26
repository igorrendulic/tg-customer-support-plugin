---
title: "Support Exchange Retrieval Requirements"
date: 2026-06-26
topic: support-exchange-retrieval
---

# Support Exchange Retrieval Requirements

## Summary

Add a derived Support Exchange layer for Telegram evidence. Raw messages remain the source of truth, while retrieval can group a requester problem with response candidates and label each response by authority: operator, peer/community, or ambiguous.

---

## Problem Frame

Telegram support history is conversational. A single message can be too terse to retrieve or understand by itself, so the current index includes nearby messages as context. That helps search recover useful support episodes, but it also lets a multi-author text blob appear under one document-level author.

This creates misleading evidence. A search hit can match a neighbor message written by a support user while the result metadata still points at the center message author. The same problem becomes riskier when non-operator users answer each other: proximity alone cannot decide which response is authoritative support truth.

---

## Key Decisions

- **Exchange over arbitrary message windows.** Retrieval should prefer a problem-and-response shape when Telegram structure supports it.
- **Authority labels over answer detection alone.** A response can be useful context without being an authoritative answer.
- **Derived layer over raw-message replacement.** Every exchange must trace back to original Telegram message IDs, and raw message evidence remains available when grouping is uncertain.
- **Partial exchanges are valid.** Unanswered questions, peer-only responses, and unclear turns should not be forced into a clean answered state.

---

## Actors

- A1. **Support Operator:** The configured human or account identity whose responses can become authoritative support evidence.
- A2. **Support User:** A Telegram participant asking for help or reporting an issue.
- A3. **Peer Participant:** A non-operator Telegram participant who may answer, speculate, or add context.
- A4. **Agent Surface:** The assistant-facing workflow that presents evidence and drafts replies for operator approval.
- A5. **Local Core:** The local implementation boundary that syncs Telegram messages, builds derived retrieval units, and returns source-linked evidence.

---

## Requirements

**Exchange Shape**

- R1. The Local Core must derive Support Exchanges from Telegram history without deleting or overwriting raw message evidence.
- R2. A Support Exchange must identify the requester problem when a non-operator support request can be inferred.
- R3. A Support Exchange may include multiple response candidates when more than one participant replies to the requester problem.
- R4. A Support Exchange must preserve source Telegram message IDs, authors, timestamps, and text for every included question or response message.
- R5. A Support Exchange may remain partial when the question, answer, or relationship between messages is unclear.

**Authority and Attribution**

- R6. Response candidates must be labeled as operator, peer/community, or ambiguous.
- R7. Only configured operator identities can produce authoritative Telegram answer evidence.
- R8. Peer/community responses may appear as context but must not be treated as policy or settled support truth.
- R9. Search result attribution must identify the matched message or matched exchange role rather than presenting a multi-author blob as one author's message.
- R10. Evidence output must distinguish the requester problem from operator responses and peer/community responses.

**Retrieval Behavior**

- R11. Search may return Support Exchange evidence when the exchange gives better support context than a raw message alone.
- R12. Search must still be able to return raw Telegram message evidence when no reliable exchange exists.
- R13. Operator-answer evidence should rank as stronger support guidance than peer/community responses when both match the query.
- R14. Peer/community responses should remain visible enough for the Support Operator to notice contested or misleading advice.
- R15. Draft context must not use peer/community responses as the basis for an authoritative reply unless corroborated by operator, Manual Knowledge, web, or Repository Evidence.

**Safety and Fallbacks**

- R16. Exchange grouping must expose confidence or ambiguity when the relationship between question and responses is uncertain.
- R17. Unanswered exchanges should be retrievable as unresolved support needs, not silently discarded.
- R18. Ambiguous response authority must be shown to the Agent Surface before any draft relies on that response.
- R19. Existing Manual Knowledge, Repository Evidence, and conflict semantics must continue to outrank Telegram peer/community responses.

---

## Key Flows

- F1. **High-confidence operator answer**
  - **Trigger:** A Support User asks a question and a configured Support Operator responds in a traceable reply or nearby turn.
  - **Actors:** A1, A2, A4, A5
  - **Steps:** The Local Core derives an exchange, labels the requester problem, labels the operator response as authoritative Telegram evidence, and returns both with source message IDs.
  - **Outcome:** The Agent Surface can cite the prior support exchange without misattributing the user request to the operator.

- F2. **Peer response before operator response**
  - **Trigger:** A Support User asks a question, a Peer Participant replies, and a Support Operator later responds.
  - **Actors:** A1, A2, A3, A4, A5
  - **Steps:** The Local Core groups response candidates, labels the peer response separately from the operator response, and ranks the operator response as stronger guidance.
  - **Outcome:** The Agent Surface can show community context without treating it as policy.

- F3. **Unclear or unanswered exchange**
  - **Trigger:** A Support User asks for help and no reliable operator response is found.
  - **Actors:** A2, A4, A5
  - **Steps:** The Local Core preserves the requester problem as a partial exchange and marks the missing or unclear answer state.
  - **Outcome:** Search can surface unresolved needs without inventing an answer.

---

## Acceptance Examples

- AE1. **Covers R2, R4, R9.** Given a search hit matches `Snuglyni` inside a multi-message Telegram context, when evidence is returned, then the result identifies `Snuglyni` as the matched requester message author rather than only showing the center message author.
- AE2. **Covers R6, R7, R8.** Given a non-operator participant answers another user's support question, when the exchange is built, then that response is labeled peer/community and is not treated as authoritative support truth.
- AE3. **Covers R3, R10, R13.** Given both a peer participant and a configured operator respond to the same requester problem, when search returns the exchange, then both responses may be visible but the operator response is distinguished as stronger guidance.
- AE4. **Covers R5, R12, R16.** Given Telegram messages cannot be grouped with enough confidence, when retrieval runs, then raw message evidence remains available and the exchange is not forced into a false answered state.
- AE5. **Covers R15, R18, R19.** Given draft context includes a peer/community response that matches the query, when the Agent Surface prepares a reply, then it does not rely on that response as policy without corroborating evidence.
- AE6. **Covers R17.** Given a Support User asks a question and no operator response is found, when the operator searches later, then the unanswered exchange can surface as an unresolved support need.

---

## Scope Boundaries

- This does not require perfect classification of every Telegram turn in v1.
- This does not remove raw Telegram message retrieval.
- This does not make peer/community answers authoritative.
- This does not create a public-facing ticketing workflow.
- This does not change Manual Knowledge or Repository Evidence authority.

---

## Dependencies / Assumptions

- Configured operator identities exist or can be identified by the support profile.
- Telegram reply links, message order, and author identities are available enough to derive high-confidence exchanges for at least common cases.
- Ambiguous cases are acceptable as partial exchanges instead of blocking the feature.

---

## Success Criteria

- Search no longer presents a multi-author Telegram context as if all text belongs to one author.
- Prior operator answers can be retrieved as support guidance without losing the requester problem that prompted them.
- Peer/community replies can be shown as context without becoming support policy.
- Unanswered or ambiguous support requests remain discoverable.
- Drafting behavior continues to prefer authoritative evidence over peer/community responses.

---

## Sources / Research

- `tg_support/indexing/chunking.py` currently builds Telegram chunk text from neighboring messages while storing metadata from the center message.
- `tests/test_chunking.py` currently expects Telegram chunks to include neighboring context.
- `tg_support/storage/db.py` preserves Telegram message IDs, authors, timestamps, text, and chunk/document metadata needed for source traceability.
- `CONCEPTS.md` defines Evidence Bundle, Manual Knowledge Note, Repository Evidence, and related authority concepts used by the support workflow.
