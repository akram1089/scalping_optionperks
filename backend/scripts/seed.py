"""Seed script — create a test user."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.auth.jwt import hash_password
from app.db import async_session
from app.models import GlobalState, User


async def seed() -> None:
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == "demo@scalpdesk.local"))
        if result.scalar_one_or_none():
            print("Seed user already exists")
            return
        user = User(email="demo@scalpdesk.local", password_hash=hash_password("demo12345"))
        db.add(user)
        gs = (await db.execute(select(GlobalState).where(GlobalState.id == 1))).scalar_one_or_none()
        if not gs:
            db.add(GlobalState(id=1, kill_switch=False))
        await db.commit()
        print("Created demo user: demo@scalpdesk.local / demo12345")


if __name__ == "__main__":
    asyncio.run(seed())
