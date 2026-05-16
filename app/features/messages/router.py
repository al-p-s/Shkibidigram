from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.core.storage import upload_file
from app.features.messages import service
from app.features.messages.schemas import (
    EditMessageRequest,
    MessageResponse,
    SendMessageRequest,
)
from app.features.users.models import User

router = APIRouter()


@router.get("/{chat_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    chat_id: str,
    limit: int = Query(50, le=100),
    before_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.get_messages(chat_id, str(current_user.id), limit, before_id, db)
    except service.MessageError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/{chat_id}/messages", response_model=MessageResponse, status_code=201)
async def send_message(
    chat_id: str,
    data: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.send_message(chat_id, str(current_user.id), data, db)
    except service.MessageError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/{chat_id}/messages/upload", response_model=MessageResponse, status_code=201)
async def send_file(
    chat_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await file.read()
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Max file size 50MB")

    object_name = f"{chat_id}/{current_user.id}/{file.filename}"
    url = await upload_file(settings.minio_bucket_media, object_name, data, file.content_type or "application/octet-stream")

    msg_type = "image" if (file.content_type or "").startswith("image/") else "file"
    msg_data = SendMessageRequest(type=msg_type)

    try:
        msg = await service.send_message(chat_id, str(current_user.id), msg_data, db)
    except service.MessageError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    from app.features.messages.models import Attachment
    attachment = Attachment(
        message_id=msg.id,
        file_url=url,
        file_name=file.filename,
        file_size=len(data),
        mime_type=file.content_type,
    )
    db.add(attachment)
    await db.commit()

    # Загружаем в новой сессии чтобы избежать кэша
    from app.core.db import AsyncSessionLocal
    async with AsyncSessionLocal() as new_db:
        msg = await service._load_message(msg.id, new_db)

        from app.features.chats.models import ChatMember
        from sqlalchemy import select
        import uuid
        from app.core.ws_manager import ws_manager

        result = await new_db.execute(
            select(ChatMember).where(ChatMember.chat_id == uuid.UUID(chat_id))
        )
        member_ids = [str(m.user_id) for m in result.scalars().all()]

        att = msg.attachments[0] if msg.attachments else None
        payload = {
            "type": "message.new",
            "message": {
                "id": str(msg.id),
                "chat_id": str(msg.chat_id),
                "sender_id": str(msg.sender_id),
                "content": msg.content,
                "type": msg.type,
                "reply_to_id": None,
                "reply_to_content": None,
                "reply_to_sender_id": None,
                "is_edited": msg.is_edited,
                "created_at": msg.created_at.isoformat(),
                "statuses": [],
                "attachments": [{
                    "id": str(att.id),
                    "file_url": f"/api/v1/chats/attachments/{str(att.id)}",
                    "file_name": att.file_name,
                    "file_size": att.file_size,
                    "mime_type": att.mime_type,
                    "preview_url": att.preview_url,
                }] if att else [],
            },
        }
        await ws_manager.broadcast_to_users(member_ids, payload)

    return msg

@router.get("/attachments/{attachment_id}")
async def get_attachment(
    attachment_id: str,
    db: AsyncSession = Depends(get_db),
):
    from app.features.messages.models import Attachment
    from sqlalchemy import select
    import uuid as uuid_mod
    from minio import S3Error
    from fastapi.responses import StreamingResponse
    from app.core.storage import get_file_stream

    result = await db.execute(
        select(Attachment).where(Attachment.id == uuid_mod.UUID(attachment_id))
    )
    att = result.scalar_one_or_none()
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    try:
        object_name = att.file_url.replace(
            f"http://{settings.minio_endpoint}/{settings.minio_bucket_media}/", ""
        )
        generator, content_type = get_file_stream(settings.minio_bucket_media, object_name)
        return StreamingResponse(
            generator,
            media_type=content_type,
            headers={"Content-Disposition": f'inline; filename="{att.file_name}"'}
        )
    except S3Error:
        raise HTTPException(status_code=404, detail="File not found")

@router.patch("/messages/{message_id}", response_model=MessageResponse)
async def edit_message(
    message_id: str,
    data: EditMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.edit_message(message_id, str(current_user.id), data, db)
    except service.MessageError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.delete("/messages/{message_id}/all", status_code=204)
async def delete_for_all(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await service.delete_for_all(message_id, str(current_user.id), db)
    except service.MessageError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete("/messages/{message_id}/me", status_code=204)
async def delete_for_me(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await service.delete_for_me(message_id, str(current_user.id), db)
    except service.MessageError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/messages/{message_id}/read", status_code=204)
async def mark_read(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await service.mark_read(message_id, str(current_user.id), db)
    except service.MessageError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
