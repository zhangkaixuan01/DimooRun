from fastapi import APIRouter

from dimoo_run.api.native import agents, deployments, packages, promotion, replay_jobs, runs, tasks

router = APIRouter(prefix="/v1")
router.include_router(agents.router)
router.include_router(packages.router)
router.include_router(deployments.router)
router.include_router(promotion.router)
router.include_router(replay_jobs.router)
router.include_router(runs.router)
router.include_router(tasks.router)
