from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from dimoo_run.api.dependencies import RequestIdHeader
from dimoo_run.core.config import Settings
from dimoo_run.gateway.route_tester import handle_live_ingress, sync_state

router = APIRouter(tags=["ingress"])


class IngressPreflightMiddleware:
    def __init__(self, app: Any, *, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if not self._handles(scope):
            await self.app(scope, receive, send)
            return

        sync_state(self.settings.database.url)
        path = str(scope.get("path") or "")
        headers = _scope_headers(scope)
        status_code, payload = handle_live_ingress(
            path=path.removeprefix("/v1/ingress/"),
            method="OPTIONS",
            headers=headers,
            body={},
            request_id=headers.get("x-request-id"),
        )
        response_headers = _correlation_headers(payload)
        response_headers.update(_cors_headers(payload))
        if status_code == 204:
            response = Response(status_code=status_code, headers=response_headers)
        else:
            response = JSONResponse(
                status_code=status_code,
                content=payload,
                headers=response_headers,
            )
        await response(scope, receive, send)

    @staticmethod
    def _handles(scope: dict[str, Any]) -> bool:
        if scope.get("type") != "http" or scope.get("method") != "OPTIONS":
            return False
        path = str(scope.get("path") or "")
        if not path.startswith("/v1/ingress/"):
            return False
        headers = _scope_headers(scope)
        return bool(headers.get("origin") and headers.get("access-control-request-method"))


async def _invoke_published_surface(
    ingress_path: str,
    request: Request,
    x_request_id: RequestIdHeader = None,
) -> Any:
    sync_state(Settings.from_env().database.url)
    try:
        body = await request.json()
    except ValueError:
        body = {}
    status_code, payload = handle_live_ingress(
        path=ingress_path,
        method=request.method,
        headers=dict(request.headers),
        body=body if isinstance(body, dict) else {"payload": body},
        request_id=x_request_id,
    )
    response_headers = _correlation_headers(payload)
    response_headers.update(_rate_limit_headers(payload))
    response_headers.update(_cors_headers(payload))
    if status_code == 204:
        return Response(status_code=status_code, headers=response_headers)
    if status_code >= 400:
        return JSONResponse(status_code=status_code, content=payload, headers=response_headers)
    return JSONResponse(status_code=status_code, content=payload, headers=response_headers)


@router.get("/v1/ingress/{ingress_path:path}", operation_id="ingress_get")
async def ingress_get(
    ingress_path: str,
    request: Request,
    x_request_id: RequestIdHeader = None,
) -> Any:
    return await _invoke_published_surface(ingress_path, request, x_request_id)


@router.post("/v1/ingress/{ingress_path:path}", operation_id="ingress_post")
async def ingress_post(
    ingress_path: str,
    request: Request,
    x_request_id: RequestIdHeader = None,
) -> Any:
    return await _invoke_published_surface(ingress_path, request, x_request_id)


@router.put("/v1/ingress/{ingress_path:path}", operation_id="ingress_put")
async def ingress_put(
    ingress_path: str,
    request: Request,
    x_request_id: RequestIdHeader = None,
) -> Any:
    return await _invoke_published_surface(ingress_path, request, x_request_id)


@router.patch("/v1/ingress/{ingress_path:path}", operation_id="ingress_patch")
async def ingress_patch(
    ingress_path: str,
    request: Request,
    x_request_id: RequestIdHeader = None,
) -> Any:
    return await _invoke_published_surface(ingress_path, request, x_request_id)


@router.delete("/v1/ingress/{ingress_path:path}", operation_id="ingress_delete")
async def ingress_delete(
    ingress_path: str,
    request: Request,
    x_request_id: RequestIdHeader = None,
) -> Any:
    return await _invoke_published_surface(ingress_path, request, x_request_id)


def _correlation_headers(payload: dict[str, Any]) -> dict[str, str]:
    headers = {}
    request_id = payload.get("request_id")
    trace_id = payload.get("trace_id")
    if isinstance(request_id, str) and request_id:
        headers["X-Request-Id"] = request_id
    if isinstance(trace_id, str) and trace_id:
        headers["X-DimooRun-Trace-Id"] = trace_id
    return headers


def _rate_limit_headers(payload: dict[str, Any]) -> dict[str, str]:
    raw_rate_limit = payload.get("rate_limit")
    if not isinstance(raw_rate_limit, dict):
        return {}

    headers = {}
    limit = raw_rate_limit.get("limit")
    remaining = raw_rate_limit.get("remaining")
    retry_after_seconds = raw_rate_limit.get("retry_after_seconds")
    if isinstance(limit, int):
        headers["X-RateLimit-Limit"] = str(limit)
    if isinstance(remaining, int):
        headers["X-RateLimit-Remaining"] = str(remaining)
    if isinstance(retry_after_seconds, int):
        headers["Retry-After"] = str(retry_after_seconds)
    return headers


def _cors_headers(payload: dict[str, Any]) -> dict[str, str]:
    raw_cors = payload.get("cors")
    if not isinstance(raw_cors, dict) or raw_cors.get("allowed") is not True:
        return {}

    origin = raw_cors.get("origin")
    if not isinstance(origin, str) or not origin:
        return {}

    headers = {
        "Access-Control-Allow-Origin": origin,
        "Vary": "Origin",
    }
    allow_methods = raw_cors.get("allow_methods")
    if isinstance(allow_methods, list):
        method_values = [str(method) for method in allow_methods if isinstance(method, str)]
        if method_values:
            headers["Access-Control-Allow-Methods"] = ", ".join(method_values)
    allow_headers = raw_cors.get("allow_headers")
    if isinstance(allow_headers, str) and allow_headers:
        headers["Access-Control-Allow-Headers"] = allow_headers
    return headers


def _scope_headers(scope: dict[str, Any]) -> dict[str, str]:
    return {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }
