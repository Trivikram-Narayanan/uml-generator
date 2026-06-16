"""
api/routers/workspaces.py  –  Team collaboration
POST /api/workspaces                  create workspace
GET  /api/workspaces                  list mine
POST /api/workspaces/{id}/invite      invite member by email
GET  /api/workspaces/{id}/members     list members
DELETE /api/workspaces/{id}/members/{uid} remove member
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import get_db
from db.models import Workspace, WorkspaceMember, User
from auth.security import get_current_user

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])

class WorkspaceCreate(BaseModel):
    name: str

class WorkspaceOut(BaseModel):
    id: str; name: str; owner_id: str; created_at: str
    model_config = {"from_attributes": True}

class InviteRequest(BaseModel):
    email: EmailStr
    role: str = "member"

class MemberOut(BaseModel):
    user_id: str; username: str; email: str; role: str

@router.post("", response_model=WorkspaceOut, status_code=201)
async def create_workspace(req: WorkspaceCreate, db=Depends(get_db), user: User=Depends(get_current_user)):
    ws = Workspace(name=req.name, owner_id=user.id)
    db.add(ws); await db.flush()
    # Add creator as owner member
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    return WorkspaceOut(id=ws.id, name=ws.name, owner_id=ws.owner_id,
                        created_at=ws.created_at.isoformat())

@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(db=Depends(get_db), user: User=Depends(get_current_user)):
    r = await db.execute(
        select(Workspace).join(WorkspaceMember,
            WorkspaceMember.workspace_id==Workspace.id)
        .where(WorkspaceMember.user_id==user.id)
    )
    rows = r.scalars().all()
    return [WorkspaceOut(id=w.id,name=w.name,owner_id=w.owner_id,
                         created_at=w.created_at.isoformat()) for w in rows]

@router.post("/{workspace_id}/invite", status_code=201)
async def invite_member(workspace_id: str, req: InviteRequest,
                         db=Depends(get_db), user: User=Depends(get_current_user)):
    await _assert_owner(workspace_id, user.id, db)
    # Find user by email
    r = await db.execute(select(User).where(User.email==req.email))
    invitee = r.scalar_one_or_none()
    if not invitee: raise HTTPException(404, "No user with that email")
    # Check not already member
    r2 = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.workspace_id==workspace_id, WorkspaceMember.user_id==invitee.id))
    if r2.scalar_one_or_none(): raise HTTPException(409, "Already a member")
    db.add(WorkspaceMember(workspace_id=workspace_id, user_id=invitee.id, role=req.role))
    return {"ok": True, "invited": invitee.username}

@router.get("/{workspace_id}/members", response_model=list[MemberOut])
async def list_members(workspace_id: str, db=Depends(get_db), user: User=Depends(get_current_user)):
    await _assert_member(workspace_id, user.id, db)
    r = await db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id==WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id==workspace_id)
    )
    return [MemberOut(user_id=u.id, username=u.username, email=u.email, role=m.role)
            for m, u in r.all()]

@router.delete("/{workspace_id}/members/{user_id}", status_code=204)
async def remove_member(workspace_id: str, user_id: str,
                         db=Depends(get_db), user: User=Depends(get_current_user)):
    await _assert_owner(workspace_id, user.id, db)
    r = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.workspace_id==workspace_id, WorkspaceMember.user_id==user_id))
    m = r.scalar_one_or_none()
    if m: await db.delete(m)

async def _assert_owner(ws_id, user_id, db):
    r = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.workspace_id==ws_id, WorkspaceMember.user_id==user_id,
        WorkspaceMember.role=="owner"))
    if not r.scalar_one_or_none(): raise HTTPException(403,"Not workspace owner")

async def _assert_member(ws_id, user_id, db):
    r = await db.execute(select(WorkspaceMember).where(
        WorkspaceMember.workspace_id==ws_id, WorkspaceMember.user_id==user_id))
    if not r.scalar_one_or_none(): raise HTTPException(403,"Not a member")
