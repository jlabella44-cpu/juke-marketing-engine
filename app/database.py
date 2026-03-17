from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for DB sessions."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def set_project_status(
    db: AsyncSession,
    project_id: UUID,
    status: str,
    error_stage: str | None = None,
    error_message: str | None = None,
) -> None:
    """Update project status atomically. All services call this — never raw assignment."""
    await db.execute(
        text(
            """
            UPDATE projects
            SET
                status        = :status,
                error_stage   = :error_stage,
                error_message = :error_message,
                updated_at    = NOW()
            WHERE id = :project_id
            """
        ),
        {
            "status": status,
            "error_stage": error_stage,
            "error_message": error_message,
            "project_id": str(project_id),
        },
    )
