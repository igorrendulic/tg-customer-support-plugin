from __future__ import annotations

from tg_support.storage.db import SupportDatabase
from tg_support.telegram_client import TelegramGateway


class PostingError(RuntimeError):
    pass


def apply_confirmation(db: SupportDatabase, token: str, gateway: TelegramGateway | None = None) -> dict:
    with db.connect() as conn:
        conf = conn.execute("SELECT * FROM confirmations WHERE token = ?", (token,)).fetchone()
        if conf is None:
            raise PostingError("Unknown confirmation token.")
        if conf["consumed_at"] is not None:
            raise PostingError("Confirmation token has already been consumed.")
        draft = conn.execute("SELECT * FROM drafts WHERE id = ?", (conf["draft_id"],)).fetchone()
        if draft is None:
            raise PostingError("Draft no longer exists.")
        conn.execute("UPDATE confirmations SET consumed_at = CURRENT_TIMESTAMP WHERE id = ?", (conf["id"],))
        if conf["action"] == "cancel":
            conn.execute("UPDATE drafts SET status = 'cancelled' WHERE id = ?", (draft["id"],))
            conn.execute("INSERT INTO post_attempts(draft_id, confirmation_id, status) VALUES (?, ?, 'cancelled')", (draft["id"], conf["id"]))
            return {"status": "cancelled", "draft_id": draft["id"]}
        if draft["target_message_id"] is None:
            conn.execute(
                "INSERT INTO post_attempts(draft_id, confirmation_id, status, error) VALUES (?, ?, 'failed', ?)",
                (draft["id"], conf["id"], "Cannot post without a reply target message."),
            )
            raise PostingError("Cannot post without a reply target message.")
        if gateway is None:
            raise PostingError("Posting requires a Telegram gateway.")
    try:
        result = gateway.send_reply(draft["target_chat"], draft["message_text"], draft["target_message_id"])
    except Exception as exc:
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO post_attempts(draft_id, confirmation_id, status, error) VALUES (?, ?, 'failed', ?)",
                (draft["id"], conf["id"], str(exc)),
            )
        raise
    with db.connect() as conn:
        conn.execute("UPDATE drafts SET status = 'posted' WHERE id = ?", (draft["id"],))
        conn.execute(
            "INSERT INTO post_attempts(draft_id, confirmation_id, status, telegram_message_id) VALUES (?, ?, 'posted', ?)",
            (draft["id"], conf["id"], result.get("message_id")),
        )
    return {"status": "posted", "draft_id": draft["id"], "telegram_message_id": result.get("message_id")}
