import asyncio
import sys
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings, validate_runtime_settings
from .monitor import monitor_loop
from .routers import auth_router, projects_router, deployments_router, flags_router, agents_router, webhooks_router, dashboard_router, notifications_router, alerts_router


def create_app(start_monitor: bool = True) -> FastAPI:
    settings = get_settings()
    validate_runtime_settings(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = None
        if start_monitor and settings.health_monitor_enabled:
            task = asyncio.create_task(monitor_loop())
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="ShipSmith Core API - Deployment and Feature Flag Control Plane",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_prefix = settings.api_prefix
    app.include_router(auth_router, prefix=api_prefix)
    app.include_router(projects_router, prefix=api_prefix)
    app.include_router(deployments_router, prefix=api_prefix)
    app.include_router(flags_router, prefix=api_prefix)
    app.include_router(agents_router, prefix=api_prefix)
    app.include_router(webhooks_router, prefix=api_prefix)
    app.include_router(dashboard_router, prefix=api_prefix)
    app.include_router(notifications_router, prefix=api_prefix)
    app.include_router(alerts_router, prefix=api_prefix)

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "service": "shipsmith-api"}

    return app


app = create_app()


def main():
    import uvicorn

    uvicorn.run(
        "shipsmith_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
