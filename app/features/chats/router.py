from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.features.chats import service
from app.features.chats.schemas import ChatResponse, CreateChatRequest, UpdateChatRequest
from app.features.users.models import User

from fastapi import File, UploadFile
import uuid
from app.core.storage import upload_file
from app.config import settings

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

@router.post("/{chat_id}/avatar", response_model=ChatResponse)
async def upload_chat_avatar(
    chat_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="Only jpg/png allowed")

    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large, max 5MB")

    object_name = f"chats/{chat_id}/avatar/{file.filename}"
    await upload_file(settings.minio_bucket_avatars, object_name, data, file.content_type)

    try:
        return await service.update_chat_avatar(chat_id, str(current_user.id), object_name, db)
    except service.ChatError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/{chat_id}/avatar")
async def get_chat_avatar(
    chat_id: str,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select as sa_select
    from app.features.chats.models import Chat
    from minio import S3Error
    from fastapi.responses import StreamingResponse
    from app.core.storage import get_file_stream

    result = await db.execute(sa_select(Chat).where(Chat.id == uuid.UUID(chat_id)))
    chat = result.scalar_one_or_none()
    if not chat or not chat.avatar_url:
        raise HTTPException(status_code=404, detail="Avatar not found")

    try:
        object_name = chat.avatar_url
        generator, content_type = get_file_stream(settings.minio_bucket_avatars, object_name)
        return StreamingResponse(generator, media_type=content_type)
    except S3Error:
        raise HTTPException(status_code=404, detail="Avatar not found")
