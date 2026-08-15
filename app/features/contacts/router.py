from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.features.contacts import service
from app.features.contacts.schemas import BlockResponse, ContactResponse
from app.features.users.models import User

router = APIRouter()


@router.get("/", response_model=list[ContactResponse])
async def get_contacts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_contacts(str(current_user.id), db)


@router.post("/{contact_id}", response_model=ContactResponse, status_code=201)
async def add_contact(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.add_contact(str(current_user.id), contact_id, db)
    except service.ContactError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete("/{contact_id}", status_code=204)
async def remove_contact(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await service.remove_contact(str(current_user.id), contact_id, db)
    except service.ContactError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/blocked", response_model=list[BlockResponse])
async def get_blocks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_blocks(str(current_user.id), db)

@router.get("/blocked/check/{user_id}", response_model=bool)
async def check_blocked_by(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.is_blocked(str(current_user.id), user_id, db)

@router.post("/blocked/{user_id}", response_model=BlockResponse, status_code=201)
async def block_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.block_user(str(current_user.id), user_id, db)
    except service.ContactError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete("/blocked/{user_id}", status_code=204)
async def unblock_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await service.unblock_user(str(current_user.id), user_id, db)
        # Уведомляем разблокированного
        from app.core.ws_manager import ws_manager
        await ws_manager.send_to_user(user_id, {
            "type": "unblocked_by",
            "user_id": str(current_user.id),
        })
    except service.ContactError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
