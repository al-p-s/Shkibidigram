import uuid
from datetime import datetime

from pydantic import BaseModel


class SendMessageRequest(BaseModel):
    content: str | None = None
    type: str = "text"
    reply_to_id: uuid.UUID | None = None


class EditMessageRequest(BaseModel):
    content: str


class AttachmentResponse(BaseModel):
    id: uuid.UUID
    file_url: str
    file_name: str | None
    file_size: int | None
    mime_type: str | None
    preview_url: str | None

    model_config = {"from_attributes": True}


class MessageStatusResponse(BaseModel):
    user_id: uuid.UUID
    status: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: uuid.UUID
    chat_id: uuid.UUID
    sender_id: uuid.UUID
    type: str
    content: str | None
    reply_to_id: uuid.UUID | None
    is_edited: bool
    is_deleted_for_all: bool
    created_at: datetime
    updated_at: datetime
    attachments: list[AttachmentResponse]
    statuses: list[MessageStatusResponse]

    model_config = {"from_attributes": True}
