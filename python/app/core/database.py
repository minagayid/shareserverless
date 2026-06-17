from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(AsyncAttrs, DeclarativeBase):
    pass


# Engine is created once at startup.
engine: AsyncEngine | None = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def init_db() -> None:
    global engine, AsyncSessionLocal
    engine = create_async_engine(
        str(settings.database_url),
        echo=settings.debug,
        pool_pre_ping=True,
    )
    AsyncSessionLocal = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )


async def get_session() -> AsyncSession:
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    async with AsyncSessionLocal() as session:
        yield session
