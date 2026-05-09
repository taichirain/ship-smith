import sys
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import auth_router, projects_router, deployments_router, flags_router, agents_router, webhooks_router, dashboard_router, notifications_router, alerts_router


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="ShipSmith Core API - Deployment and Feature Flag Control Plane",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
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
