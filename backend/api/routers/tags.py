"""
api/routers/tags.py
GET    /api/tags               list user's tags
POST   /api/tags               create tag
DELETE /api/tags/{id}          delete tag
POST   /api/diagrams/{id}/tags attach tag to diagram
DELETE /api/diagrams/{id}/tags/{tag_id} remove tag from diagram
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import get_db
from db.models import Tag, DiagramTag, Diagram, User
from auth.security import get_current_user

router = APIRouter(tags=["tags"])

class TagCreate(BaseModel):
    name: str; color: str = "#4f8ef7"

class TagOut(BaseModel):
    id: str; name: str; color: str
    model_config = {"from_attributes": True}

@router.get("/api/tags", response_model=list[TagOut])
async def list_tags(db=Depends(get_db), user: User=Depends(get_current_user)):
    r = await db.execute(select(Tag).where(Tag.user_id==user.id))
    return r.scalars().all()

@router.post("/api/tags", response_model=TagOut, status_code=201)
async def create_tag(req: TagCreate, db=Depends(get_db), user: User=Depends(get_current_user)):
    t = Tag(user_id=user.id, name=req.name.strip(), color=req.color)
    db.add(t); await db.flush(); return t

@router.delete("/api/tags/{tag_id}", status_code=204)
async def delete_tag(tag_id: str, db=Depends(get_db), user: User=Depends(get_current_user)):
    r = await db.execute(select(Tag).where(Tag.id==tag_id, Tag.user_id==user.id))
    t = r.scalar_one_or_none()
    if not t: raise HTTPException(404)
    await db.delete(t)

@router.post("/api/diagrams/{diagram_id}/tags/{tag_id}", status_code=201)
async def attach_tag(diagram_id:str, tag_id:str, db=Depends(get_db), user:User=Depends(get_current_user)):
    r = await db.execute(select(Diagram).where(Diagram.id==diagram_id,Diagram.user_id==user.id))
    if not r.scalar_one_or_none(): raise HTTPException(404,"Diagram not found")
    dt = DiagramTag(diagram_id=diagram_id, tag_id=tag_id)
    db.add(dt)
    return {"ok": True}

@router.delete("/api/diagrams/{diagram_id}/tags/{tag_id}", status_code=204)
async def remove_tag(diagram_id:str, tag_id:str, db=Depends(get_db), user:User=Depends(get_current_user)):
    r = await db.execute(select(DiagramTag).where(
        DiagramTag.diagram_id==diagram_id, DiagramTag.tag_id==tag_id))
    dt = r.scalar_one_or_none()
    if dt: await db.delete(dt)
