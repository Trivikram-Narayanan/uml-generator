"""
api/routers/versions.py
GET  /api/diagrams/{id}/versions       list all versions
GET  /api/diagrams/{id}/versions/{v}   get specific version
POST /api/diagrams/{id}/restore/{v}    restore to version
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from db.database import get_db
from db.models import DiagramVersion, Diagram, User
from auth.security import get_current_user
from datetime import datetime

router = APIRouter(prefix="/api/diagrams", tags=["versions"])

class VersionOut(BaseModel):
    id: str; version: int; change_note: str | None
    plantuml_code: str; impl_code: str | None; impl_language: str | None
    created_at: str

@router.get("/{diagram_id}/versions", response_model=list[VersionOut])
async def list_versions(
    diagram_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _check_owner(diagram_id, user.id, db)
    result = await db.execute(
        select(DiagramVersion)
        .where(DiagramVersion.diagram_id == diagram_id)
        .order_by(desc(DiagramVersion.version))
    )
    rows = result.scalars().all()
    return [_vout(v) for v in rows]

@router.post("/{diagram_id}/restore/{version_num}")
async def restore_version(
    diagram_id: str, version_num: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    diag = await _check_owner(diagram_id, user.id, db)
    result = await db.execute(
        select(DiagramVersion).where(
            DiagramVersion.diagram_id == diagram_id,
            DiagramVersion.version == version_num,
        )
    )
    ver = result.scalar_one_or_none()
    if not ver: raise HTTPException(404, "Version not found")

    new_version = diag.version + 1
    diag.plantuml_code = ver.plantuml_code
    diag.impl_code     = ver.impl_code
    diag.impl_language = ver.impl_language
    diag.version       = new_version
    diag.updated_at    = datetime.utcnow()
    # Save restored state as a new version entry
    db.add(DiagramVersion(
        diagram_id=diagram_id, version=new_version,
        plantuml_code=ver.plantuml_code, impl_code=ver.impl_code,
        impl_language=ver.impl_language,
        change_note=f"restored to version {version_num}",
    ))
    await db.flush()
    return {"ok": True, "restored_to": version_num}

async def _check_owner(diagram_id, user_id, db):
    r = await db.execute(select(Diagram).where(Diagram.id==diagram_id, Diagram.user_id==user_id))
    d = r.scalar_one_or_none()
    if not d: raise HTTPException(404,"Diagram not found")
    return d

def _vout(v: DiagramVersion) -> VersionOut:
    return VersionOut(id=v.id, version=v.version, change_note=v.change_note,
        plantuml_code=v.plantuml_code, impl_code=v.impl_code,
        impl_language=v.impl_language, created_at=v.created_at.isoformat())
