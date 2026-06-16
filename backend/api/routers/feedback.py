"""
api/routers/feedback.py
POST /api/feedback          submit thumbs up/down + optional correction
GET  /api/feedback/stats    aggregated scores (for RAG improvement later)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from db.database import get_db
from db.models import DiagramFeedback, Diagram, User
from auth.security import get_current_user

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

class FeedbackRequest(BaseModel):
    diagram_id: str
    score: int           # 1 = thumbs up, -1 = thumbs down
    correction: str | None = None

@router.post("", status_code=201)
async def submit_feedback(
    req: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if req.score not in (1, -1):
        raise HTTPException(400, "score must be 1 or -1")

    # Check diagram exists and is accessible
    result = await db.execute(select(Diagram).where(Diagram.id == req.diagram_id))
    diag = result.scalar_one_or_none()
    if not diag:
        raise HTTPException(404, "Diagram not found")

    # Upsert feedback
    existing = await db.execute(
        select(DiagramFeedback).where(
            DiagramFeedback.diagram_id == req.diagram_id,
            DiagramFeedback.user_id == user.id,
        )
    )
    fb = existing.scalar_one_or_none()
    if fb:
        fb.score = req.score
        fb.correction = req.correction
    else:
        fb = DiagramFeedback(
            diagram_id=req.diagram_id,
            user_id=user.id,
            score=req.score,
            correction=req.correction,
        )
        db.add(fb)

    # Update diagram thumb_score
    avg = await db.execute(
        select(func.avg(DiagramFeedback.score))
        .where(DiagramFeedback.diagram_id == req.diagram_id)
    )
    diag.thumb_score = float(avg.scalar() or 0)
    return {"ok": True}
