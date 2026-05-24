from fastapi import APIRouter

from dimoo_run.api.admin import router as admin_router
from dimoo_run.api.native import router as native_router
from dimoo_run.core.health import HealthResponse, get_health

router = APIRouter()
router.include_router(native_router)
router.include_router(admin_router)


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return get_health()
