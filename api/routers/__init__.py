# api/routers/__init__.py

from api.routers.habitats import router as habitats_router
from api.routers.species import router as species_router
from api.routers.sensors import router as sensors_router
from api.routers.outlets import router as outlets_router
from api.routers.thresholds import router as thresholds_router
from api.routers.rules import router as rules_router
from api.routers.daynight import router as daynight_router
from api.routers.alerts import router as alerts_router
from api.routers.status import router as status_router
from api.routers.dashboard import router as dashboard_router

__all__ = [
    "habitats_router",
    "species_router",
    "sensors_router",
    "outlets_router",
    "thresholds_router",
    "rules_router",
    "daynight_router",
    "alerts_router",
    "status_router",
    "dashboard_router"
]
