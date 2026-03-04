"""Storage endpoints: upload, list, get, delete data sources (bank statements / bridge files)."""

import os
import uuid

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import get_settings
from app.core.constants import UPLOAD_CHUNK_SIZE
from app.models.data_source import DataSource
from app.models.bank_entry import BankEntry
from app.models.bridge_mapping import BridgeMapping
from app.schemas.schemas import DataSourceOut, DataSourceUploadResponse

router = APIRouter()


async def _save_chunked(upload: UploadFile, dest: str) -> None:
    """Stream upload to disk in chunks to avoid OOM."""
    async with aiofiles.open(dest, "wb") as f:
        while True:
            chunk = await upload.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            await f.write(chunk)


@router.post("/storage/bank-statement", response_model=DataSourceUploadResponse)
async def upload_bank_statement(
    file: UploadFile = File(...),
    name: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    ds = DataSource(
        name=name,
        source_type="bank_statement",
        filename=file.filename or "unknown.xlsx",
        file_path="",  # set below
        status="uploading",
    )
    db.add(ds)
    await db.flush()

    dest = os.path.join(settings.UPLOAD_DIR, f"ds_{ds.id}_bank_{file.filename}")
    await _save_chunked(file, dest)
    ds.file_path = dest
    ds.status = "parsing"
    await db.commit()

    # Dispatch Celery parse task
    from app.tasks.parse_bank_statement import parse_bank_statement
    parse_bank_statement.delay(str(ds.id), dest)

    return DataSourceUploadResponse(
        data_source_id=ds.id,
        name=ds.name,
        source_type="bank_statement",
        filename=ds.filename,
        message="Bank statement uploaded, parsing started",
    )


@router.post("/storage/bridge-file", response_model=DataSourceUploadResponse)
async def upload_bridge_file(
    file: UploadFile = File(...),
    name: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    ds = DataSource(
        name=name,
        source_type="bridge_file",
        filename=file.filename or "unknown.txt",
        file_path="",
        status="uploading",
    )
    db.add(ds)
    await db.flush()

    dest = os.path.join(settings.UPLOAD_DIR, f"ds_{ds.id}_bridge_{file.filename}")
    await _save_chunked(file, dest)
    ds.file_path = dest
    ds.status = "parsing"
    await db.commit()

    from app.tasks.parse_bridge_file import parse_bridge_file
    parse_bridge_file.delay(str(ds.id), dest)

    return DataSourceUploadResponse(
        data_source_id=ds.id,
        name=ds.name,
        source_type="bridge_file",
        filename=ds.filename,
        message="Bridge file uploaded, parsing started",
    )


@router.get("/storage", response_model=list[DataSourceOut])
async def list_data_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DataSource).order_by(DataSource.created_at.desc())
    )
    return [DataSourceOut.model_validate(ds) for ds in result.scalars().all()]


@router.get("/storage/{ds_id}", response_model=DataSourceOut)
async def get_data_source(ds_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DataSource).where(DataSource.id == ds_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    return DataSourceOut.model_validate(ds)


@router.delete("/storage/{ds_id}")
async def delete_data_source(ds_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DataSource).where(DataSource.id == ds_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")

    # Delete parsed data
    if ds.source_type == "bank_statement":
        await db.execute(delete(BankEntry).where(BankEntry.data_source_id == ds_id))
    elif ds.source_type == "bridge_file":
        await db.execute(delete(BridgeMapping).where(BridgeMapping.data_source_id == ds_id))

    # Delete file from disk
    if ds.file_path and os.path.exists(ds.file_path):
        os.remove(ds.file_path)

    await db.delete(ds)
    await db.commit()

    return {"message": "Data source deleted", "id": str(ds_id)}
