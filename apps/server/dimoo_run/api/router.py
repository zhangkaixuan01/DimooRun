from fastapi import APIRouter

from dimoo_run.core.health import HealthResponse, get_health

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return get_health()
