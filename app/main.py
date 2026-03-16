from fastapi import FastAPI

from app.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="Juke Media AI Marketing Engine",
        version="0.1.0",
        debug=settings.DEBUG,
    )

    # Router inclusion placeholder — add routers here as tasks are completed
    # from app.api import router as api_router
    # app.include_router(api_router, prefix="/api/v1")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
