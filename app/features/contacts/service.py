import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.contacts.models import Block, Contact
from app.features.users.models import User


class ContactError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code


async def get_contacts(user_id: str, db: AsyncSession) -> list[Contact]:
    result = await db.execute(
        select(Contact)
        .where(Contact.owner_id == uuid.UUID(user_id))
        .options(selectinload(Contact.contact))
    )
    return list(result.scalars().all())


async def add_contact(user_id: str, contact_id: str, db: AsyncSession) -> Contact:
    if user_id == contact_id:
        raise ContactError("Cannot add yourself")

    result = await db.execute(select(User).where(User.id == uuid.UUID(contact_id)))
    if not result.scalar_one_or_none():
        raise ContactError("User not found", status_code=404)

    existing = await db.execute(
        select(Contact).where(
            Contact.owner_id == uuid.UUID(user_id),
            Contact.contact_id == uuid.UUID(contact_id),
        )
    )
    if existing.scalar_one_or_none():
        raise ContactError("Already in contacts")

    contact = Contact(
        owner_id=uuid.UUID(user_id),
        contact_id=uuid.UUID(contact_id),
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)

    result = await db.execute(
        select(Contact)
        .where(Contact.id == contact.id)
        .options(selectinload(Contact.contact))
    )
    return result.scalar_one()


async def remove_contact(user_id: str, contact_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(Contact).where(
            Contact.owner_id == uuid.UUID(user_id),
            Contact.contact_id == uuid.UUID(contact_id),
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise ContactError("Contact not found", status_code=404)

    await db.delete(contact)
    await db.commit()


async def get_blocks(user_id: str, db: AsyncSession) -> list[Block]:
    result = await db.execute(
        select(Block)
        .where(Block.blocker_id == uuid.UUID(user_id))
        .options(selectinload(Block.blocked))
    )
    return list(result.scalars().all())


async def block_user(user_id: str, blocked_id: str, db: AsyncSession) -> Block:
    if user_id == blocked_id:
        raise ContactError("Cannot block yourself")

    result = await db.execute(select(User).where(User.id == uuid.UUID(blocked_id)))
    if not result.scalar_one_or_none():
        raise ContactError("User not found", status_code=404)

    existing = await db.execute(
        select(Block).where(
            Block.blocker_id == uuid.UUID(user_id),
            Block.blocked_id == uuid.UUID(blocked_id),
        )
    )
    if existing.scalar_one_or_none():
        raise ContactError("Already blocked")

    block = Block(
        blocker_id=uuid.UUID(user_id),
        blocked_id=uuid.UUID(blocked_id),
    )
    db.add(block)
    await db.commit()

    result = await db.execute(
        select(Block)
        .where(Block.id == block.id)
        .options(selectinload(Block.blocked))
    )
    block = result.scalar_one()

    # Уведомляем заблокированного через WS
    from app.core.ws_manager import ws_manager
    await ws_manager.send_to_user(blocked_id, {
        "type": "blocked_by",
        "user_id": user_id,
    })

    return block


async def unblock_user(user_id: str, blocked_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(Block).where(
            Block.blocker_id == uuid.UUID(user_id),
            Block.blocked_id == uuid.UUID(blocked_id),
        )
    )
    block = result.scalar_one_or_none()
    if not block:
        raise ContactError("Block not found", status_code=404)

    await db.delete(block)
    await db.commit()


async def is_blocked(user_id: str, other_id: str, db: AsyncSession) -> bool:
    result = await db.execute(
        select(Block).where(
            Block.blocker_id == uuid.UUID(other_id),
            Block.blocked_id == uuid.UUID(user_id),
        )
    )
    return result.scalar_one_or_none() is not None
