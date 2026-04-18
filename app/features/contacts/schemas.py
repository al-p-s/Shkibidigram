import uuid
from datetime import datetime

from pydantic import BaseModel

from app.features.users.schemas import UserPublicResponse


class ContactResponse(BaseModel):
    id: uuid.UUID
    contact: UserPublicResponse
    created_at: datetime

    model_config = {"from_attributes": True}


class BlockResponse(BaseModel):
    id: uuid.UUID
    blocked: UserPublicResponse
    created_at: datetime

    model_config = {"from_attributes": True}
