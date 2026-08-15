import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property

from app.core.db import Base


class Chat(Base):
    __tablename__ = "chat"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    members: Mapped[list["ChatMember"]] = relationship(back_populates="chat", cascade="all, delete-orphan")
    messages: Mapped[list["Message"]] = relationship(back_populates="chat", cascade="all, delete-orphan")  # noqa

    __table_args__ = (
        CheckConstraint("type IN ('direct', 'group')"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.unread_count = 0
        self.last_message_at = None


class ChatMember(Base):
    __tablename__ = "chat_member"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="member", nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_read_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("message.id"), nullable=True)

    chat: Mapped["Chat"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()  # noqa

    __table_args__ = (
        UniqueConstraint("chat_id", "user_id"),
        CheckConstraint("role IN ('owner', 'admin', 'member')"),
    )
