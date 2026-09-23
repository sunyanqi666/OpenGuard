from fastapi import APIRouter

from app.api.routes import (
    associations,
    audit_logs,
    components,
    dashboard,
    items,
    login,
    private,
    remediations,
    transfers,
    users,
    utils,
    vulnerabilities,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(vulnerabilities.router)
api_router.include_router(components.router)
api_router.include_router(associations.router)
api_router.include_router(dashboard.router)
api_router.include_router(remediations.router)
api_router.include_router(audit_logs.router)
api_router.include_router(transfers.router)


if settings.FASTAPI_ENV == "development":
    api_router.include_router(private.router)
