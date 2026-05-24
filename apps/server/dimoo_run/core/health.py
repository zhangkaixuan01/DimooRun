from pydantic import BaseModel

from dimoo_run import __version__


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


def get_health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="dimoorun-server",
        version=__version__,
    )
