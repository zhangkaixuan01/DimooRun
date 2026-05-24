from fastapi import APIRouter

from dimoo_run.api.native import agents, deployments, runs, tasks

router = APIRouter(prefix="/v1")
router.include_router(agents.router)
router.include_router(deployments.router)
router.include_router(runs.router)
router.include_router(tasks.router)
