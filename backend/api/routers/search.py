"""
api/routers/search.py
GET /api/search?q=...&type=...&tag=...&folder=...
Full-text search across title + description + diagram_type
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, desc
from db.database import get_db
from db.models import Diagram, DiagramTag, Tag, User
from auth.security import get_current_user
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/search", tags=["search"])

class SearchResult(BaseModel):
    id: str; title: str; description: str; diagram_type: str
    impl_language: str | None; updated_at: str; folder: str | None

@router.get("", response_model=list[SearchResult])
async def search(
    q: Optional[str] = Query(None),
    diagram_type: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    folder: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Diagram).where(Diagram.user_id == user.id)

    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Diagram.title.ilike(like),
            Diagram.description.ilike(like),
        ))
    if diagram_type:
        stmt = stmt.where(Diagram.diagram_type == diagram_type)
    if folder:
        stmt = stmt.where(Diagram.folder == folder)
    if tag:
        stmt = stmt.join(DiagramTag, DiagramTag.diagram_id==Diagram.id)\
                   .join(Tag, Tag.id==DiagramTag.tag_id)\
                   .where(Tag.name==tag)

    stmt = stmt.order_by(desc(Diagram.updated_at)).limit(limit)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [SearchResult(
        id=d.id, title=d.title, description=d.description,
        diagram_type=d.diagram_type, impl_language=d.impl_language,
        updated_at=d.updated_at.isoformat(), folder=d.folder,
    ) for d in rows]
