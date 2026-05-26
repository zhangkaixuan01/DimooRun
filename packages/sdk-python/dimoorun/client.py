from typing import Any
from uuid import uuid4

import httpx


class DimooRunAPIError(RuntimeError):
    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        request_id: str | None,
        details: dict[str, Any],
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.request_id = request_id
        self.details = details


class DimooRun:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )

    def create_run(
        self,
        *,
        agent_id: str,
        input: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        response = self._client.post(
            f"/v1/agents/{agent_id}/tasks",
            json={"input": input},
            headers={"Idempotency-Key": idempotency_key or f"sdk-{uuid4().hex}"},
        )
        if response.is_error:
            self._raise_api_error(response)
        payload = response.json()
        if not isinstance(payload, dict):
            raise DimooRunAPIError(
                error_code="invalid_response",
                message="Expected a JSON object response.",
                request_id=None,
                details={},
            )
        return dict(payload)

    def _raise_api_error(self, response: httpx.Response) -> None:
        payload = response.json()
        raise DimooRunAPIError(
            error_code=str(payload.get("error_code", "unknown")),
            message=str(payload.get("message", response.text)),
            request_id=payload.get("request_id"),
            details=dict(payload.get("details") or {}),
        )
