from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.features.chats import service
from app.features.chats.schemas import ChatResponse, CreateChatRequest, UpdateChatRequest
from app.features.users.models import User

router = APIRouter()


@router.get("/", response_model=list[ChatResponse])
async def get_chats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_user_chats(str(current_user.id), db)


@router.post("/", response_model=ChatResponse, status_code=201)
async def create_chat(
    data: CreateChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.create_chat(data, str(current_user.id), db)
    except service.ChatError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.get_chat(chat_id, str(current_user.id), db)
    except service.ChatError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.patch("/{chat_id}", response_model=ChatResponse)
async def update_chat(
    chat_id: str,
    data: UpdateChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.update_chat(chat_id, str(current_user.id), data, db)
    except service.ChatError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/{chat_id}/members/{user_id}", response_model=ChatResponse)
async def add_member(
    chat_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.add_member(chat_id, str(current_user.id), user_id, db)
    except service.ChatError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete("/{chat_id}/leave", status_code=204)
async def leave_chat(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await service.leave_chat(chat_id, str(current_user.id), db)
    except service.ChatError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
