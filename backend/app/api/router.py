"""Top-level API router registration."""

from fastapi import APIRouter

from app.api.routes import (
    action_executions,
    actions,
    assistant,
    audit_logs,
    functions,
    health,
    links,
    objects,
    ontology,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(ontology.router, prefix="/api/v1/ontology", tags=["ontology"])
api_router.include_router(objects.router, prefix="/api/v1/objects", tags=["objects"])
api_router.include_router(links.router, prefix="/api/v1/links", tags=["links"])
api_router.include_router(
    functions.router,
    prefix="/api/v1/functions",
    tags=["functions"],
)
api_router.include_router(actions.router, prefix="/api/v1/actions", tags=["actions"])
api_router.include_router(
    action_executions.router,
    prefix="/api/v1/action-executions",
    tags=["action-executions"],
)
api_router.include_router(
    audit_logs.router,
    prefix="/api/v1/audit-logs",
    tags=["audit-logs"],
)
api_router.include_router(
    assistant.router,
    prefix="/api/v1/assistant",
    tags=["assistant"],
)
