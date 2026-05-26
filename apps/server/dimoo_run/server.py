from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dimoo_run.api.router import router
from dimoo_run.core.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    app = FastAPI(title="DimooRun API", version="0.1.0")
    if resolved_settings.console.enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved_settings.console.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(router)
    return app


app = create_app()
