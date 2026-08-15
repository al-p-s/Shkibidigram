import uuid
from datetime import datetime

from pydantic import BaseModel

from app.features.users.schemas import UserPublicResponse


class CreateChatRequest(BaseModel):
    type: str
    name: str | None = None
    member_ids: list[uuid.UUID]


class ChatMemberResponse(BaseModel):
    id: uuid.UUID
    user: UserPublicResponse
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    id: uuid.UUID
    type: str
    name: str | None
    description: str | None
    avatar_url: str | None
    created_at: datetime
    members: list[ChatMemberResponse]
    unread_count: int = 0
    last_message_at: datetime | None = None

    model_config = {"from_attributes": True}


class UpdateChatRequest(BaseModel):
    name: str | None = None
    description: str | None = None
