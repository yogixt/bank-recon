"""History endpoints: list all sessions, get session detail."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.session import ReconciliationSession
from app.schemas.schemas import SessionOut

router = APIRouter()


@router.get("/history", response_model=list[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ReconciliationSession).order_by(ReconciliationSession.created_at.desc())
    )
    return [SessionOut.model_validate(s) for s in result.scalars().all()]


@router.get("/history/{session_id}", response_model=SessionOut)
async def get_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ReconciliationSession).where(ReconciliationSession.id == session_id)
    )
    sess = result.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionOut.model_validate(sess)
