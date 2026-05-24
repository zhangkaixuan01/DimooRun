from fastapi import APIRouter

from dimoo_run.api.admin import router as admin_routes

router = APIRouter(prefix="/v1")
router.include_router(admin_routes.router)
