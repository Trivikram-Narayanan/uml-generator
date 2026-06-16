"""
api/routers/templates.py
GET  /api/templates          list all (builtin + user-created)
POST /api/templates          create from existing diagram
GET  /api/templates/{id}     get one
POST /api/templates/{id}/use increment use_count, return diagram data
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, desc
from db.database import get_db
from db.models import Template, Diagram, User
from auth.security import get_current_user
from typing import Optional

router = APIRouter(prefix="/api/templates", tags=["templates"])

class TemplateOut(BaseModel):
    id: str; title: str; description: str; diagram_type: str
    plantuml_code: str; category: str | None; is_builtin: bool; use_count: int

class CreateTemplateRequest(BaseModel):
    diagram_id: str
    title: Optional[str] = None
    category: Optional[str] = None

@router.get("", response_model=list[TemplateOut])
async def list_templates(db=Depends(get_db)):
    r = await db.execute(
        select(Template).order_by(desc(Template.use_count), desc(Template.is_builtin))
    )
    return r.scalars().all()

@router.get("/{template_id}", response_model=TemplateOut)
async def get_template(template_id: str, db=Depends(get_db)):
    r = await db.execute(select(Template).where(Template.id==template_id))
    t = r.scalar_one_or_none()
    if not t: raise HTTPException(404)
    return t

@router.post("/{template_id}/use")
async def use_template(template_id: str, db=Depends(get_db)):
    r = await db.execute(select(Template).where(Template.id==template_id))
    t = r.scalar_one_or_none()
    if not t: raise HTTPException(404)
    t.use_count += 1
    return {"plantuml_code": t.plantuml_code, "description": t.description,
            "diagram_type": t.diagram_type}

@router.post("", response_model=TemplateOut, status_code=201)
async def create_template(req: CreateTemplateRequest, db=Depends(get_db),
                           user: User=Depends(get_current_user)):
    r = await db.execute(select(Diagram).where(
        Diagram.id==req.diagram_id, Diagram.user_id==user.id))
    diag = r.scalar_one_or_none()
    if not diag: raise HTTPException(404,"Diagram not found")
    t = Template(
        title=req.title or diag.title, description=diag.description,
        diagram_type=diag.diagram_type, plantuml_code=diag.plantuml_code,
        category=req.category, is_builtin=False,
    )
    db.add(t); await db.flush(); return t
