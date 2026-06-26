from __future__ import annotations

from collections import defaultdict
from typing import Any

from tg_support.storage.db import ExchangeMemberInput, SupportDatabase, SupportExchangeInput, SupportExchangeRecord


def rebuild_support_exchanges(db: SupportDatabase, operator_identities: tuple[str, ...] = ()) -> list[SupportExchangeRecord]:
    rows = db.telegram_message_author_rows()
    operators = {identity.casefold().removeprefix("@") for identity in operator_identities if identity.strip()}
    replies_by_parent: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    rows_by_key = {(row["chat_id"], row["telegram_message_id"]): row for row in rows}

    for row in rows:
        reply_to = row.get("reply_to_message_id")
        if reply_to is not None:
            replies_by_parent[(row["chat_id"], int(reply_to))].append(row)

    response_message_ids = {row["id"] for replies in replies_by_parent.values() for row in replies}
    exchanges: list[SupportExchangeInput] = []
    requester_ids = set()

    for key, replies in sorted(replies_by_parent.items(), key=lambda item: (item[0][0], item[0][1])):
        requester = rows_by_key.get(key)
        if requester is None or _is_operator(requester, operators):
            continue
        requester_ids.add(requester["id"])
        members = [ExchangeMemberInput(requester["id"], "requester", "none", 0)]
        ordered_replies = sorted(replies, key=lambda row: (row["telegram_message_id"], row["id"]))
        has_operator = False
        has_peer = False
        for ordinal, reply in enumerate(ordered_replies, start=1):
            if _is_operator(reply, operators):
                role = "operator_response"
                authority = "operator"
                has_operator = True
            else:
                role = "peer_response"
                authority = "peer"
                has_peer = True
            members.append(ExchangeMemberInput(reply["id"], role, authority, ordinal))
        status = _status(has_operator, has_peer)
        confidence = 1.0 if has_operator else 0.75
        exchanges.append(
            SupportExchangeInput(
                chat_id=requester["chat_id"],
                status=status,
                confidence=confidence,
                members=tuple(members),
                metadata={"strategy": "reply_link"},
            )
        )

    for row in rows:
        if row["id"] in requester_ids or row["id"] in response_message_ids or _is_operator(row, operators):
            continue
        if not str(row.get("text") or "").strip():
            continue
        exchanges.append(
            SupportExchangeInput(
                chat_id=row["chat_id"],
                status="unanswered",
                confidence=0.5,
                members=(ExchangeMemberInput(row["id"], "requester", "none", 0),),
                metadata={"strategy": "unanswered"},
            )
        )

    return db.replace_support_exchanges(exchanges)


def _is_operator(row: dict[str, Any], operators: set[str]) -> bool:
    if not operators:
        return False
    identities = row.get("author_identities") or []
    return any(str(identity).casefold().removeprefix("@") in operators for identity in identities)


def _status(has_operator: bool, has_peer: bool) -> str:
    if has_operator:
        return "answered_by_operator"
    if has_peer:
        return "peer_response_only"
    return "ambiguous"
