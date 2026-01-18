# api/main.py

"""
Reptilia API - FastAPI backend for the React Native frontend.

This API provides REST endpoints for managing reptile habitats,
reading sensor data, controlling outlets, and more.

Run with: uvicorn api.main:app --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings
from api.database import get_database, close_connection
from api.routers import (
    habitats_router,
    species_router,
    sensors_router,
    outlets_router,
    thresholds_router,
    rules_router,
    daynight_router,
    alerts_router,
    status_router,
    dashboard_router
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup: verify database connection
    db = get_database()
    try:
        db.command("ping")
        print(f"Connected to MongoDB: {db.name}")
    except Exception as e:
        print(f"Warning: Could not connect to MongoDB: {e}")

    yield

    # Shutdown: close database connection
    close_connection()
    print("Closed MongoDB connection")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description="REST API for the Reptile Habitat Automation System",
        lifespan=lifespan
    )

    # Configure CORS for React Native
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers with API prefix
    prefix = settings.api_prefix
    app.include_router(habitats_router, prefix=prefix)
    app.include_router(species_router, prefix=prefix)
    app.include_router(sensors_router, prefix=prefix)
    app.include_router(outlets_router, prefix=prefix)
    app.include_router(thresholds_router, prefix=prefix)
    app.include_router(rules_router, prefix=prefix)
    app.include_router(daynight_router, prefix=prefix)
    app.include_router(alerts_router, prefix=prefix)
    app.include_router(status_router, prefix=prefix)
    app.include_router(dashboard_router, prefix=prefix)

    @app.get("/")
    def root():
        """Root endpoint with API information."""
        return {
            "name": settings.api_title,
            "version": settings.api_version,
            "docs": "/docs",
            "openapi": "/openapi.json"
        }

    @app.get("/health")
    def health():
        """Simple health check endpoint."""
        return {"status": "ok"}

    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
