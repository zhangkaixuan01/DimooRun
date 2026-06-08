from fastapi import APIRouter

from dimoo_run.api import auth as auth_router
from dimoo_run.api import ingress as live_ingress_router
from dimoo_run.api.admin import backups as backup_router
from dimoo_run.api.admin import datasets as dataset_router
from dimoo_run.api.admin import experiments as experiment_router
from dimoo_run.api.admin import incidents as incident_router
from dimoo_run.api.admin import ingress_routes as ingress_route_router
from dimoo_run.api.admin import model_gateways as model_gateway_router
from dimoo_run.api.admin import notifications as notification_router
from dimoo_run.api.admin import policies as policy_router
from dimoo_run.api.admin import published_surfaces as published_surface_router
from dimoo_run.api.admin import router as admin_router
from dimoo_run.api.admin import secrets as secret_router
from dimoo_run.api.admin import tools as tool_router
from dimoo_run.api.compat import router as compat_router
from dimoo_run.api.console import published as console_published_router
from dimoo_run.api.console import router as console_router
from dimoo_run.api.native import router as native_router
from dimoo_run.core.health import HealthResponse, get_health

router = APIRouter()
router.include_router(auth_router.router)
router.include_router(native_router)
router.include_router(live_ingress_router.router)
router.include_router(console_router)
router.include_router(console_published_router.router)
router.include_router(policy_router.router)
router.include_router(published_surface_router.router)
router.include_router(ingress_route_router.router)
router.include_router(dataset_router.router)
router.include_router(experiment_router.router)
router.include_router(incident_router.router)
router.include_router(notification_router.router)
router.include_router(backup_router.router)
router.include_router(model_gateway_router.router)
router.include_router(tool_router.router)
router.include_router(secret_router.router)
router.include_router(admin_router)
router.include_router(compat_router)


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return get_health()
