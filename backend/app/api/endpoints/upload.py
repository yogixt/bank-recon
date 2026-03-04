"""Upload endpoints: only transaction IDs (bank statement + bridge file moved to /storage)."""

import os
import uuid

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import get_settings
from app.core.constants import UPLOAD_CHUNK_SIZE
from app.models.session import ReconciliationSession
from app.schemas.schemas import UploadResponse

router = APIRouter()


async def _save_chunked(upload: UploadFile, dest: str) -> None:
    """Stream upload to disk in chunks to avoid OOM."""
    async with aiofiles.open(dest, "wb") as f:
        while True:
            chunk = await upload.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            await f.write(chunk)


async def _get_or_create_session(
    session_id: str | None, db: AsyncSession
) -> ReconciliationSession:
    if session_id:
        uid = uuid.UUID(session_id)
        result = await db.execute(
            select(ReconciliationSession).where(ReconciliationSession.id == uid)
        )
        sess = result.scalar_one_or_none()
        if sess:
            return sess
    sess = ReconciliationSession()
    db.add(sess)
    await db.flush()
    return sess


@router.post("/upload/transaction-ids", response_model=UploadResponse)
async def upload_transaction_ids(
    file: UploadFile = File(...),
    session_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    sess = await _get_or_create_session(session_id, db)
    dest = os.path.join(settings.UPLOAD_DIR, f"{sess.id}_txn_{file.filename}")
    await _save_chunked(file, dest)
    sess.transaction_ids_file = file.filename
    sess.transaction_ids_path = dest
    await db.commit()
    return UploadResponse(
        session_id=sess.id,
        file_type="transaction_ids",
        filename=file.filename,
        message="Transaction IDs uploaded",
    )


@router.post("/upload/paste", response_model=UploadResponse)
async def paste_transaction_ids(
    text: str,
    session_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Accept pasted transaction IDs as raw text."""
    settings = get_settings()
    sess = await _get_or_create_session(session_id, db)
    dest = os.path.join(settings.UPLOAD_DIR, f"{sess.id}_txn_paste.txt")
    async with aiofiles.open(dest, "w") as f:
        await f.write(text)
    sess.transaction_ids_file = "paste_input.txt"
    sess.transaction_ids_path = dest
    await db.commit()
    return UploadResponse(
        session_id=sess.id,
        file_type="transaction_ids",
        filename="paste_input.txt",
        message="Pasted transaction IDs saved",
    )
