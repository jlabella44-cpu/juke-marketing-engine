from fastapi import APIRouter, Response
from sqlalchemy import text

from app.config import settings
from app.database import engine

router = APIRouter()


@router.get("/health")
async def health(response: Response) -> dict:
    # Check DB
    db_status = "ok"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    # Check Redis
    redis_status = "ok"
    try:
        import redis

        r = redis.Redis.from_url(settings.REDIS_URL)
        r.ping()
    except Exception:
        redis_status = "error"

    status_code = 200 if db_status == "ok" and redis_status == "ok" else 503
    response.status_code = status_code
    return {"status": "ok" if status_code == 200 else "degraded", "db": db_status, "redis": redis_status}
