"""
api/routers/diagrams.py  –  Core diagram endpoints (v2)
POST /api/diagrams/generate-full    generate diagram + code (auto-saves version)
POST /api/diagrams/generate-code    regen code for existing diagram
POST /api/diagrams/refine           iterative refinement ("fix this part")
GET  /api/diagrams                  list (with search/filter)
POST /api/diagrams                  manual save
GET  /api/diagrams/{id}
PATCH /api/diagrams/{id}
DELETE /api/diagrams/{id}
GET  /api/diagrams/public/{id}
"""
from __future__ import annotations
import os, base64, logging
from datetime import datetime
from typing import Optional
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, or_

from db.database import get_db
from db.models import Diagram, DiagramVersion, User
from auth.security import get_current_user
from rag.retriever import retrieve
from rag.prompt_builder import build_prompt
from llm.local_llm import generate_uml
from llm.code_generator import generate_code, SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/diagrams", tags=["diagrams"])

DIAGRAM_TYPES = ["sequence","class","usecase","activity","component","state","er"]
KROKI_URL     = os.getenv("KROKI_URL","https://kroki.io")


# ── Schemas ───────────────────────────────────────────────────────────────────

class FullGenerateRequest(BaseModel):
    description:  str  = Field(..., min_length=5, max_length=2000)
    diagram_type: str  = Field(default="sequence")
    language:     str  = Field(default="python")
    render_png:   bool = Field(default=False)
    save:         bool = Field(default=True)
    title:        Optional[str] = None
    folder:       Optional[str] = None
    workspace_id: Optional[str] = None

class RefineRequest(BaseModel):
    diagram_id:    str
    instruction:   str = Field(..., min_length=3, max_length=500)
    language:      str = Field(default="python")
    change_note:   Optional[str] = None

class CodeRequest(BaseModel):
    plantuml_code: str
    diagram_type:  str = "sequence"
    language:      str = "python"

class SaveRequest(BaseModel):
    title: str; description: str; diagram_type: str
    plantuml_code: str; impl_code: Optional[str]=None
    impl_language: Optional[str]=None; is_public: bool=False
    folder: Optional[str]=None; workspace_id: Optional[str]=None

class PatchRequest(BaseModel):
    title:     Optional[str]  = None
    is_public: Optional[bool] = None
    folder:    Optional[str]  = None

class ChunkInfo(BaseModel):
    text:str; source:str; diagram_type:str; content_type:str; score:float

class DiagramOut(BaseModel):
    id:str; title:str; description:str; diagram_type:str
    plantuml_code:str; impl_code:Optional[str]; impl_language:Optional[str]
    is_public:bool; folder:Optional[str]; version:int; llm_backend:Optional[str]
    thumb_score:float; created_at:str; updated_at:str
    model_config = {"from_attributes":True}

class GenerateResponse(BaseModel):
    plantuml_code:str; diagram_type:str; implementation:dict
    retrieved_chunks:list[ChunkInfo]; backend_used:str; model_used:str
    fallback_used:bool; png_base64:Optional[str]=None
    render_error:Optional[str]=None; saved_id:Optional[str]=None


# ── Generate ──────────────────────────────────────────────────────────────────

@router.post("/generate-full", response_model=GenerateResponse)
async def generate_full(
    req: FullGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _vt(req.diagram_type); _vl(req.language)
    chunks  = retrieve(req.description, req.diagram_type, top_k=6)
    prompt  = build_prompt(req.description, req.diagram_type, chunks)
    uml_res = generate_uml(req.description, req.diagram_type, prompt)
    code_res= generate_code(uml_res["code"], req.diagram_type, req.language)

    png_b64, render_err = None, None
    if req.render_png:
        png_b64, render_err = await _render_png(uml_res["code"])

    saved_id = None
    if req.save:
        title = req.title or _auto_title(req.description)
        diag = Diagram(
            user_id=user.id, workspace_id=req.workspace_id,
            title=title, description=req.description,
            diagram_type=req.diagram_type, plantuml_code=uml_res["code"],
            impl_code=code_res.get("code"), impl_language=req.language,
            llm_backend=uml_res.get("backend"), folder=req.folder,
        )
        db.add(diag); await db.flush()
        # Save first version
        db.add(DiagramVersion(
            diagram_id=diag.id, version=1,
            plantuml_code=uml_res["code"],
            impl_code=code_res.get("code"), impl_language=req.language,
            change_note="initial generation",
        ))
        await db.flush()
        saved_id = diag.id

    return GenerateResponse(
        plantuml_code=uml_res["code"], diagram_type=req.diagram_type,
        implementation=code_res,
        retrieved_chunks=[ChunkInfo(text=c.text,source=c.source,
            diagram_type=c.diagram_type,content_type=c.content_type,score=c.score)
            for c in chunks],
        backend_used=uml_res["backend"], model_used=uml_res.get("model",""),
        fallback_used=uml_res["fallback"],
        png_base64=png_b64, render_error=render_err, saved_id=saved_id,
    )


@router.post("/generate-code")
async def generate_code_ep(req: CodeRequest, user: User=Depends(get_current_user)):
    _vt(req.diagram_type); _vl(req.language)
    return generate_code(req.plantuml_code, req.diagram_type, req.language)


@router.post("/refine", response_model=GenerateResponse)
async def refine_diagram(
    req: RefineRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Iterative refinement — apply a natural-language instruction to existing diagram."""
    diag = await _get_owned(req.diagram_id, user.id, db)
    _vl(req.language)

    # Build refinement prompt
    refine_prompt = (
        f"You have an existing PlantUML diagram:\n\n{diag.plantuml_code}\n\n"
        f"Apply this change: {req.instruction}\n\n"
        f"Output ONLY the complete updated PlantUML diagram starting with @startuml."
    )
    uml_res  = generate_uml(diag.description, diag.diagram_type, refine_prompt)
    code_res = generate_code(uml_res["code"], diag.diagram_type, req.language)

    new_version = diag.version + 1
    diag.plantuml_code = uml_res["code"]
    diag.impl_code     = code_res.get("code")
    diag.impl_language = req.language
    diag.version       = new_version
    diag.updated_at    = datetime.utcnow()
    # Save the new state as the next version
    db.add(DiagramVersion(
        diagram_id=diag.id, version=new_version,
        plantuml_code=uml_res["code"], impl_code=code_res.get("code"),
        impl_language=req.language,
        change_note=req.change_note or req.instruction[:100],
    ))
    await db.flush()

    return GenerateResponse(
        plantuml_code=uml_res["code"], diagram_type=diag.diagram_type,
        implementation=code_res, retrieved_chunks=[],
        backend_used=uml_res["backend"], model_used=uml_res.get("model",""),
        fallback_used=uml_res["fallback"], saved_id=diag.id,
    )


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[DiagramOut])
async def list_diagrams(
    folder: Optional[str]=Query(None),
    limit:int=20, offset:int=0,
    db=Depends(get_db), user: User=Depends(get_current_user),
):
    stmt = select(Diagram).where(Diagram.user_id==user.id)
    if folder: stmt = stmt.where(Diagram.folder==folder)
    stmt = stmt.order_by(desc(Diagram.updated_at)).limit(limit).offset(offset)
    r = await db.execute(stmt)
    return [_dout(d) for d in r.scalars().all()]

@router.post("", response_model=DiagramOut, status_code=201)
async def save_diagram(req: SaveRequest, db=Depends(get_db), user: User=Depends(get_current_user)):
    _vt(req.diagram_type)
    d = Diagram(user_id=user.id, title=req.title, description=req.description,
        diagram_type=req.diagram_type, plantuml_code=req.plantuml_code,
        impl_code=req.impl_code, impl_language=req.impl_language,
        is_public=req.is_public, folder=req.folder, workspace_id=req.workspace_id)
    db.add(d); await db.flush(); return _dout(d)

@router.get("/{diagram_id}", response_model=DiagramOut)
async def get_diagram(diagram_id:str, db=Depends(get_db), user: User=Depends(get_current_user)):
    return _dout(await _get_owned(diagram_id, user.id, db))

@router.patch("/{diagram_id}", response_model=DiagramOut)
async def update_diagram(diagram_id:str, req: PatchRequest,
                          db=Depends(get_db), user: User=Depends(get_current_user)):
    d = await _get_owned(diagram_id, user.id, db)
    if req.title     is not None: d.title     = req.title
    if req.is_public is not None: d.is_public = req.is_public
    if req.folder    is not None: d.folder    = req.folder
    await db.flush(); return _dout(d)

@router.delete("/{diagram_id}", status_code=204)
async def delete_diagram(diagram_id:str, db=Depends(get_db), user: User=Depends(get_current_user)):
    d = await _get_owned(diagram_id, user.id, db)
    await db.delete(d)

@router.get("/public/{diagram_id}", response_model=DiagramOut)
async def get_public(diagram_id:str, db=Depends(get_db)):
    r = await db.execute(select(Diagram).where(Diagram.id==diagram_id,Diagram.is_public==True))
    d = r.scalar_one_or_none()
    if not d: raise HTTPException(404)
    return _dout(d)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _vt(dt):
    if dt not in DIAGRAM_TYPES: raise HTTPException(400,f"diagram_type must be one of {DIAGRAM_TYPES}")

def _vl(lang):
    if lang not in SUPPORTED_LANGUAGES: raise HTTPException(400,f"language must be one of {SUPPORTED_LANGUAGES}")

async def _get_owned(diagram_id, user_id, db):
    r = await db.execute(select(Diagram).where(Diagram.id==diagram_id,Diagram.user_id==user_id))
    d = r.scalar_one_or_none()
    if not d: raise HTTPException(404,"Diagram not found")
    return d

def _dout(d: Diagram) -> DiagramOut:
    return DiagramOut(id=d.id,title=d.title,description=d.description,
        diagram_type=d.diagram_type,plantuml_code=d.plantuml_code,
        impl_code=d.impl_code,impl_language=d.impl_language,
        is_public=d.is_public,folder=d.folder,version=d.version,
        llm_backend=d.llm_backend,thumb_score=d.thumb_score or 0.0,
        created_at=d.created_at.isoformat(),updated_at=d.updated_at.isoformat())

def _auto_title(desc: str) -> str:
    words = desc.strip().split()
    return " ".join(words[:8]) + ("…" if len(words)>8 else "")

async def _render_png(code: str):
    try:
        import zlib
        c = zlib.compress(code.encode("utf-8"),9)
        enc = base64.urlsafe_b64encode(c).decode("ascii")
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"{KROKI_URL}/plantuml/png/{enc}")
            r.raise_for_status()
            return base64.b64encode(r.content).decode("ascii"), None
    except Exception as e:
        return None, str(e)
