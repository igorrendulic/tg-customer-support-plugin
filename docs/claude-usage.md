# Claude Usage

Claude should call the same CLI commands documented in `agents/claude.md`.

Use stats commands for direct counts, search commands for evidence, and draft commands for reply preparation. For product-behavior, capability, API-behavior, or debugging questions, use `scripts/tg-support repo-evidence "<query>"`. Repository Evidence from the configured branch outranks Manual Knowledge Notes, Telegram evidence, and web evidence; show stale checkout warnings before relying on it.

Claude must not post directly or infer confirmation. Posting requires the explicit confirmation token produced for the exact draft shown to the operator.
