from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from minio import S3Error
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid as uuid_mod

from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.core.storage import upload_file
from app.config import settings
from fastapi.responses import StreamingResponse
from app.core.storage import get_file_stream
from app.features.users import service
from app.features.users.models import User
from app.features.users.schemas import UpdateProfileRequest, UserPublicResponse, UserResponse
from app.features.realtime.online import get_online_statuses



router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    data: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.update_profile(str(current_user.id), data, db)
    except service.UserError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/me/avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="Only jpg/png allowed")

    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large, max 5MB")

    object_name = f"{current_user.id}/avatar/{file.filename}"
    await upload_file(settings.minio_bucket_avatars, object_name, data, file.content_type)
    try:
        return await service.update_avatar(str(current_user.id), object_name, db)
    except service.UserError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)





@router.get("/search", response_model=UserPublicResponse | None)
async def search_user(
    username: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not username:
        raise HTTPException(status_code=400, detail="Provide username or email")

    return await service.search_by_username(username, str(current_user.id), db)


@router.post("/online", response_model=dict[str, bool])
async def check_online(
    user_ids: list[str],
    current_user: User = Depends(get_current_user),
):
    return await get_online_statuses(user_ids)

@router.get("/{user_id}/avatar")
async def get_user_avatar(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):

    user_uuid = uuid_mod.UUID(user_id)
    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if not user or not user.avatar_url:
        raise HTTPException(status_code=404, detail="Avatar not found")

    try:
        if user.avatar_url.startswith("http://"):
            object_name = user.avatar_url.replace(f"http://{settings.minio_endpoint}/{settings.minio_bucket_avatars}/",
                                                  "")
        else:
            object_name = user.avatar_url
        generator, content_type = get_file_stream(settings.minio_bucket_avatars, object_name)
        return StreamingResponse(generator, media_type=content_type)
    except S3Error:
        raise HTTPException(status_code=404, detail="Avatar not found")

@router.get("/{user_id}/public", response_model=UserPublicResponse)
async def get_user_public_profile(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.get_public_profile(user_id, db)
    except service.UserError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
