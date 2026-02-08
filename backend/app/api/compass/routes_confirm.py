"""Compass confirm and share APIs (memories, loops, portraits)."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


class ConfirmRequest(BaseModel):
    status: str


class ShareRequest(BaseModel):
    visibility: str


class PortraitEditRequest(BaseModel):
    portrait_text: Optional[str] = None
    portrait_facets_json: Optional[dict] = None
    facets_json: Optional[dict] = None


# ---- Memories ----
@router.post("/memories/{memory_id}/confirm")
async def confirm_memory(
    memory_id: str,
    body: ConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm or reject a memory (owner only)."""
    from app.infra.db.repositories.memory_repo import MemoryRepository
    from app.infra.db.models.compass import MemoryModel
    from sqlalchemy import select
    repo = MemoryRepository(db)
    result = await db.execute(select(MemoryModel).where(MemoryModel.memory_id == memory_id))
    mem = result.scalar_one_or_none()
    if not mem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    if mem.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the owner of this memory")
    if body.status not in ("confirmed", "rejected"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status must be confirmed or rejected")
    ok = await repo.update_status(memory_id, body.status)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return {"ok": True}


@router.post("/memories/{memory_id}/share")
async def share_memory(
    memory_id: str,
    body: ShareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update memory visibility (owner only)."""
    from app.infra.db.repositories.memory_repo import MemoryRepository
    from app.infra.db.models.compass import MemoryModel
    from sqlalchemy import select
    repo = MemoryRepository(db)
    result = await db.execute(select(MemoryModel).where(MemoryModel.memory_id == memory_id))
    mem = result.scalar_one_or_none()
    if not mem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    if mem.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the owner of this memory")
    if body.visibility not in ("private", "shared_with_partner", "shared_with_group"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid visibility")
    ok = await repo.update_visibility(memory_id, body.visibility)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return {"ok": True}


# ---- Loops ----
@router.post("/loops/{loop_id}/confirm")
async def confirm_loop(
    loop_id: str,
    body: ConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm or reject a relationship loop (member of relationship only)."""
    from app.infra.db.repositories.loop_repo import LoopRepository
    from app.infra.db.models.compass import RelationshipLoopModel
    from app.infra.db.models.relationship import relationship_members
    from sqlalchemy import select
    result = await db.execute(select(RelationshipLoopModel).where(RelationshipLoopModel.loop_id == loop_id))
    loop = result.scalar_one_or_none()
    if not loop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loop not found")
    mem_result = await db.execute(
        select(relationship_members.c.user_id).where(
            relationship_members.c.relationship_id == loop.relationship_id,
        )
    )
    member_ids = [row[0] for row in mem_result.all()]
    if current_user.id not in member_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this relationship")
    if body.status not in ("confirmed", "rejected"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status must be confirmed or rejected")
    repo = LoopRepository(db)
    ok = await repo.update_status(loop_id, body.status)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loop not found")
    return {"ok": True}


# ---- Person portraits ----
@router.post("/person-portraits/{portrait_id}/edit")
async def edit_person_portrait(
    portrait_id: str,
    body: PortraitEditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Edit a person portrait (owner only)."""
    from app.infra.db.models.compass import PersonPortraitModel
    from sqlalchemy import select
    result = await db.execute(select(PersonPortraitModel).where(PersonPortraitModel.portrait_id == portrait_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person portrait not found")
    if p.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the owner of this portrait")
    if body.portrait_text is not None:
        p.portrait_text = body.portrait_text
    if body.portrait_facets_json is not None:
        p.portrait_facets_json = body.portrait_facets_json
    from datetime import datetime
    p.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(p)
    return {"ok": True}


@router.post("/person-portraits/{portrait_id}/share")
async def share_person_portrait(
    portrait_id: str,
    body: ShareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update person portrait visibility (owner only)."""
    from app.infra.db.models.compass import PersonPortraitModel
    from sqlalchemy import select
    result = await db.execute(select(PersonPortraitModel).where(PersonPortraitModel.portrait_id == portrait_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person portrait not found")
    if p.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the owner of this portrait")
    if body.visibility not in ("private", "shared_with_partner", "shared_with_group"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid visibility")
    p.visibility = body.visibility
    from datetime import datetime
    p.updated_at = datetime.utcnow()
    await db.commit()
    return {"ok": True}


# ---- Dyad portraits ----
@router.post("/dyad-portraits/{dyad_portrait_id}/edit")
async def edit_dyad_portrait(
    dyad_portrait_id: str,
    body: PortraitEditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Edit a dyad portrait (member of relationship only)."""
    from app.infra.db.models.compass import DyadPortraitModel
    from app.infra.db.models.relationship import relationship_members
    from sqlalchemy import select
    result = await db.execute(
        select(DyadPortraitModel).where(DyadPortraitModel.dyad_portrait_id == dyad_portrait_id)
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dyad portrait not found")
    mem_result = await db.execute(
        select(relationship_members.c.user_id).where(
            relationship_members.c.relationship_id == p.relationship_id,
        )
    )
    member_ids = [row[0] for row in mem_result.all()]
    if current_user.id not in member_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this relationship")
    if body.portrait_text is not None:
        p.portrait_text = body.portrait_text
    if body.facets_json is not None:
        p.facets_json = body.facets_json
    if body.portrait_facets_json is not None:
        p.facets_json = body.portrait_facets_json
    from datetime import datetime
    p.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(p)
    return {"ok": True}
