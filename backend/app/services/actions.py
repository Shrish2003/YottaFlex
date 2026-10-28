from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.time import now_utc
from backend.app.models.entities import CorrectiveAction
from backend.app.models.enums import CorrectiveActionStatus, CorrectiveActionType


def create_corrective_action(
    session: Session,
    *,
    excursion_id: str,
    assigned_to: str,
    action_type: CorrectiveActionType,
    description: str,
    created_at: datetime | None = None,
) -> CorrectiveAction:
    existing_ids = set(session.scalars(select(CorrectiveAction.action_id)).all())
    number = 1
    while f"ACT-{number:06d}" in existing_ids:
        number += 1
    action = CorrectiveAction(
        action_id=f"ACT-{number:06d}",
        excursion_id=excursion_id,
        assigned_to=assigned_to,
        action_type=action_type,
        description=description,
        created_at=created_at or now_utc(),
        status=CorrectiveActionStatus.OPEN,
    )
    session.add(action)
    session.flush()
    return action
