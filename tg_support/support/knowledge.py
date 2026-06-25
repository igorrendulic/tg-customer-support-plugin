from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from tg_support.storage.db import SupportDatabase


class KnowledgeError(ValueError):
    pass


@dataclass(frozen=True)
class ManualKnowledgeInput:
    text: str
    effective_date: str
    expires_date: str | None = None
    caveats: str | None = None


def parse_iso_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise KnowledgeError(f"{field} must be an ISO date in YYYY-MM-DD format.") from exc


def validate_manual_note(data: ManualKnowledgeInput) -> ManualKnowledgeInput:
    text = data.text.strip()
    if not text:
        raise KnowledgeError("Manual knowledge note text is required.")
    effective = parse_iso_date(data.effective_date.strip(), "effective_date")
    expires_raw = data.expires_date.strip() if data.expires_date else None
    if expires_raw:
        expires = parse_iso_date(expires_raw, "expires_date")
        if expires < effective:
            raise KnowledgeError("expires_date must be on or after effective_date.")
    caveats = data.caveats.strip() if data.caveats else None
    return ManualKnowledgeInput(text=text, effective_date=effective.isoformat(), expires_date=expires_raw, caveats=caveats)


def save_manual_note(db: SupportDatabase, data: ManualKnowledgeInput) -> dict:
    note = validate_manual_note(data)
    note_id = db.create_manual_note(
        note.text,
        note.effective_date,
        expires_date=note.expires_date,
        caveats=note.caveats,
        metadata={"source": "manual"},
    )
    return {
        "note_id": note_id,
        "text": note.text,
        "effective_date": note.effective_date,
        "expires_date": note.expires_date,
        "caveats": note.caveats,
    }
