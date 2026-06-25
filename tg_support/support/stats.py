from __future__ import annotations

import re
from collections import Counter

from tg_support.storage.db import SupportDatabase


LINK_RE = re.compile(r"https?://\S+")


def message_count(db: SupportDatabase, since: str | None = None) -> int:
    with db.connect() as conn:
        if since:
            return int(conn.execute("SELECT COUNT(*) AS c FROM messages WHERE sent_at >= ?", (since,)).fetchone()["c"])
        return int(conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()["c"])


def active_users(db: SupportDatabase, limit: int = 10) -> list[dict]:
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT COALESCE(author_username, 'unknown') AS user, COUNT(*) AS messages
            FROM messages GROUP BY user ORDER BY messages DESC, user ASC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def replied_to_users(db: SupportDatabase, limit: int = 10) -> list[dict]:
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT COALESCE(parent.author_username, 'unknown') AS user, COUNT(*) AS replies
            FROM messages child
            JOIN messages parent
              ON parent.chat_id = child.chat_id
             AND parent.telegram_message_id = child.reply_to_message_id
            WHERE child.reply_to_message_id IS NOT NULL
            GROUP BY user ORDER BY replies DESC, user ASC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def link_usage(db: SupportDatabase, limit: int = 10) -> list[dict]:
    counter: Counter[str] = Counter()
    with db.connect() as conn:
        for row in conn.execute("SELECT text FROM messages"):
            counter.update(link.rstrip(".,)") for link in LINK_RE.findall(row["text"]))
        for row in conn.execute("SELECT url, COUNT(*) AS count FROM pages WHERE status = 'ok' GROUP BY url"):
            counter[f"resource:{row['url']}"] += row["count"]
    return [{"link": link, "count": count} for link, count in counter.most_common(limit)]
