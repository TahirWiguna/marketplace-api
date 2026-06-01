import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, RefreshToken


@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession):
    """Test that a User can be created and persisted."""
    user = User(
        email="test@example.com",
        password_hash="hashed_password_123",
    )
    db_session.add(user)
    await db_session.flush()

    # Refresh to get server-defaults populated
    await db_session.refresh(user)

    assert user.id is not None
    assert isinstance(user.id, uuid.UUID)
    assert user.email == "test@example.com"
    assert user.password_hash == "hashed_password_123"
    assert user.created_at is not None
    assert user.updated_at is not None

    # Verify it's queryable
    result = await db_session.execute(select(User).where(User.email == "test@example.com"))
    fetched = result.scalar_one()
    assert fetched.id == user.id


@pytest.mark.asyncio
async def test_create_refresh_token(db_session: AsyncSession):
    """Test that a RefreshToken can be created and persisted."""
    user = User(
        email="tokenuser@example.com",
        password_hash="hashed_password_456",
    )
    db_session.add(user)
    await db_session.flush()

    token = RefreshToken(
        user_id=user.id,
        token_hash="abc123hash",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db_session.add(token)
    await db_session.flush()
    await db_session.refresh(token)

    assert token.id is not None
    assert isinstance(token.id, uuid.UUID)
    assert token.user_id == user.id
    assert token.token_hash == "abc123hash"
    assert token.revoked is False
    assert token.created_at is not None
    # SQLite returns naive datetimes; compare accordingly
    expires = token.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    assert expires > datetime.now(timezone.utc)

    # Verify it's queryable
    result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == "abc123hash")
    )
    fetched = result.scalar_one()
    assert fetched.id == token.id


@pytest.mark.asyncio
async def test_user_token_relationship(db_session: AsyncSession):
    """Test the bidirectional relationship between User and RefreshToken."""
    user = User(
        email="reluser@example.com",
        password_hash="hashed_password_789",
    )
    db_session.add(user)
    await db_session.flush()

    token1 = RefreshToken(
        user_id=user.id,
        token_hash="hash_one",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    token2 = RefreshToken(
        user_id=user.id,
        token_hash="hash_two",
        expires_at=datetime.now(timezone.utc) + timedelta(days=14),
    )
    db_session.add_all([token1, token2])
    await db_session.flush()

    # Refresh user to load the relationship
    await db_session.refresh(user, ["refresh_tokens"])

    assert len(user.refresh_tokens) == 2
    token_hashes = {t.token_hash for t in user.refresh_tokens}
    assert token_hashes == {"hash_one", "hash_two"}

    # Test back-populates from token to user
    await db_session.refresh(token1, ["user"])
    assert token1.user.id == user.id
    assert token1.user.email == "reluser@example.com"
