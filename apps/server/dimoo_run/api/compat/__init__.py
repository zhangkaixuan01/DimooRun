from fastapi import APIRouter

from dimoo_run.api.compat import agent_protocol, langgraph

router = APIRouter(prefix="/compat")
router.include_router(langgraph.router)
router.include_router(agent_protocol.router)
