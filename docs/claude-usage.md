# Claude Usage

Claude should call the same CLI commands documented in `agents/claude.md`.

Use stats commands for direct counts, search commands for evidence, and draft commands for reply preparation. For product-behavior, capability, API-behavior, or debugging questions, use `scripts/tg-support repo-evidence "<query>"`. Repository Evidence from the configured branch outranks Manual Knowledge Notes, Telegram evidence, and web evidence; show stale checkout warnings before relying on it.

When `draft-context` returns `evidence_sufficiency`, show its state and reasons before drafting. If a direct answer is not supported, or Repository Evidence is stale, offer both a cautious evidence-limited answer and a DM follow-up for missing support-blocking details. Do not save the DM follow-up as Manual Knowledge or cite it as evidence.

Claude must not post directly or infer confirmation. Posting requires the explicit confirmation token produced for the exact draft shown to the operator.
