import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class Contact(Base):
    __tablename__ = "contact"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    owner: Mapped["User"] = relationship(foreign_keys=[owner_id])  # noqa
    contact: Mapped["User"] = relationship(foreign_keys=[contact_id])  # noqa

    __table_args__ = (
        UniqueConstraint("owner_id", "contact_id"),
        CheckConstraint("owner_id <> contact_id"),
    )


class Block(Base):
    __tablename__ = "block"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    blocker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    blocked_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    blocker: Mapped["User"] = relationship(foreign_keys=[blocker_id])  # noqa
    blocked: Mapped["User"] = relationship(foreign_keys=[blocked_id])  # noqa

    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id"),
        CheckConstraint("blocker_id <> blocked_id"),
    )
