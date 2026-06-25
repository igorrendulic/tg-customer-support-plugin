# Reply Workflow

Run `status` first. If the profile is not ready, follow the setup preflight in `../SKILL.md` instead of drafting from an incomplete corpus.

1. Ask for the target username or Telegram message ID if neither is provided.
2. Run `scripts/tg-support draft-context --user <username>` or `scripts/tg-support draft-context --message-id <id>`.
3. Draft the reply in natural language using the returned `history`, `thread`, and `evidence`.
4. Create a draft with `draft-create` so the exact message has post and cancel confirmation tokens.
5. Show the operator:
   - target chat
   - target user or message ID
   - exact proposed message text
   - whether posting will be a reply
   - short evidence list with source IDs, URLs, or Telegram message references
   - the available `post` and `cancel` choices
6. Ask for explicit `post` or `cancel`.
7. If the operator confirms, run `confirm <post_token>`.
8. If the operator cancels, run `confirm <cancel_token>`.

Do not post if the target message is missing. The CLI will reject reply posting without a target message ID.
