from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_manager.db.models import TimelapseNote, utc_now


def list_timelapse_notes(db: Session, printer_id: int) -> list[TimelapseNote]:
    return list(
        db.scalars(
            select(TimelapseNote)
            .where(TimelapseNote.printer_id == printer_id)
            .order_by(TimelapseNote.updated_at.desc(), TimelapseNote.id.desc())
        ).all()
    )


def upsert_timelapse_note(
    db: Session,
    *,
    printer_id: int,
    path: str,
    favorite: bool | None = None,
    note: str | None = None,
    note_set: bool = False,
    cached_metadata: dict[str, Any] | None = None,
    cached_metadata_set: bool = False,
) -> TimelapseNote:
    row = db.scalars(
        select(TimelapseNote).where(TimelapseNote.printer_id == printer_id, TimelapseNote.path == path)
    ).first()
    if row is None:
        row = TimelapseNote(printer_id=printer_id, path=path, favorite=False, note=None, cached_metadata={})
        db.add(row)
    if favorite is not None:
        row.favorite = favorite
    if note_set:
        row.note = note
    if cached_metadata_set:
        row.cached_metadata = cached_metadata
    row.updated_at = utc_now()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
