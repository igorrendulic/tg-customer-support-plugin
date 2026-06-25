from __future__ import annotations

import json
from secrets import token_urlsafe

from tg_support.storage.db import SupportDatabase


def create_draft(db: SupportDatabase, target_chat: str, message_text: str, evidence: dict, target_user: str | None = None, target_message_id: int | None = None) -> dict:
    with db.connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO drafts(target_chat, target_user, target_message_id, message_text, evidence_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (target_chat, target_user, target_message_id, message_text, json.dumps(evidence, sort_keys=True)),
        )
        draft_id = int(cur.lastrowid)
        post_token = token_urlsafe(18)
        cancel_token = token_urlsafe(18)
        conn.execute("INSERT INTO confirmations(draft_id, token, action) VALUES (?, ?, 'post')", (draft_id, post_token))
        conn.execute("INSERT INTO confirmations(draft_id, token, action) VALUES (?, ?, 'cancel')", (draft_id, cancel_token))
    return {"draft_id": draft_id, "post_token": post_token, "cancel_token": cancel_token}
