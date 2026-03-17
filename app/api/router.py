from fastapi import APIRouter

from app.api import health, projects

router = APIRouter(prefix="/api")
router.include_router(health.router)
router.include_router(projects.router)
