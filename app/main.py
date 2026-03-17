from fastapi import FastAPI

from app.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="Juke Media AI Marketing Engine",
        version="0.1.0",
        debug=settings.DEBUG,
    )

    from app.api.router import router as api_router
    app.include_router(api_router)

    return app


app = create_app()
