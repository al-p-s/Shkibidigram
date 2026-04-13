import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.features.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.features.users.models import Session, User


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code


async def register(data: RegisterRequest, db: AsyncSession) -> TokenResponse:
    # проверяем уникальность
    existing = await db.execute(
        select(User).where(
            (User.email == data.email) | (User.username == data.username)
        )
    )
    if existing.scalar_one_or_none():
        raise AuthError("User with this email or username already exists")

    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        display_name=data.display_name or data.username,
    )
    db.add(user)
    await db.flush()  # получаем id до commit

    tokens = _create_tokens(str(user.id))
    session = Session(
        user_id=user.id,
        token_hash=_hash_token(tokens.refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(session)
    await db.commit()

    return tokens


async def login(data: LoginRequest, db: AsyncSession) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        raise AuthError("Invalid email or password", status_code=401)

    if not user.is_active:
        raise AuthError("Account is disabled", status_code=403)

    tokens = _create_tokens(str(user.id))
    session = Session(
        user_id=user.id,
        token_hash=_hash_token(tokens.refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(session)
    await db.commit()

    return tokens


async def refresh(refresh_token: str, db: AsyncSession) -> TokenResponse:
    user_id = decode_token(refresh_token)
    if not user_id:
        raise AuthError("Invalid or expired refresh token", status_code=401)

    token_hash = _hash_token(refresh_token)
    result = await db.execute(
        select(Session).where(Session.token_hash == token_hash)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise AuthError("Session not found", status_code=401)

    # инвалидируем старую сессию (ломаем ноги)
    await db.delete(session)

    tokens = _create_tokens(user_id)
    new_session = Session(
        user_id=uuid.UUID(user_id),
        token_hash=_hash_token(tokens.refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(new_session)
    await db.commit()

    return tokens


async def logout(refresh_token: str, db: AsyncSession) -> None:
    token_hash = _hash_token(refresh_token)
    result = await db.execute(
        select(Session).where(Session.token_hash == token_hash)
    )
    session = result.scalar_one_or_none()
    if session:
        await db.delete(session)
        await db.commit()


def _create_tokens(user_id: str) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
