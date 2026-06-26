# Reply Workflow

Run `status` first. If the profile is not ready, follow the setup preflight in `../SKILL.md` instead of drafting from an incomplete corpus.

1. Ask for the target username or Telegram message ID if neither is provided.
2. Run `scripts/tg-support draft-context --user <username>` or `scripts/tg-support draft-context --message-id <id>`.
3. If the reply depends on product behavior, supported capabilities, API behavior, or a debugging cause, run `scripts/tg-support repo-evidence "<query>"`.
4. If Repository Evidence returns a warning, show it before drafting. If Repository Evidence disagrees with Manual Knowledge Notes, Telegram evidence, or web evidence, treat Repository Evidence as higher priority and say that code is guiding the answer.
5. If the returned `conflicts` list is not empty, show the Manual Knowledge Note, older evidence, and fresher evidence to the operator and ask which source should guide the reply before drafting.
6. Show `evidence_sufficiency.state` and any returned sufficiency reason messages in the evidence summary.
7. If `target.language` is present, draft the reply in that language. Treat `translated_text` as helper context for understanding evidence, not as a reason to answer in English. If the target language is uncertain, show the language assumption before creating the draft.
8. If `evidence_sufficiency.direct_answer_supported` is true and Repository Evidence has no stale warning, draft one direct reply in natural language using the returned `history`, `thread`, `evidence`, and any Repository Evidence. Manual Knowledge Note and Repository Evidence should be cited in the evidence list when present.
9. If `evidence_sufficiency.direct_answer_supported` is false, or Repository Evidence has a stale warning, present two options before creating a draft:
   - cautious evidence-limited answer using only what the evidence supports
   - DM follow-up asking only for the missing support-blocking private or account-specific information
10. Do not save DM follow-up wording as a Manual Knowledge Note, and do not describe it as evidence.
11. After the operator chooses the exact reply option, create a draft with `draft-create` so that message has post and cancel confirmation tokens.
12. Show the operator:
   - target chat
   - target user or message ID
   - target language or language assumption when present
   - exact proposed message text
   - whether posting will be a reply
   - evidence sufficiency state and reasons when present
   - short evidence list with source IDs, URLs, Telegram message references, Manual Knowledge Note IDs, or repository paths and line ranges
   - the available `post` and `cancel` choices
13. Ask for explicit `post` or `cancel`.
14. If the operator confirms, run `confirm <post_token>`.
15. If the operator cancels, run `confirm <cancel_token>`.

Do not post if the target message is missing. The CLI will reject reply posting without a target message ID.
