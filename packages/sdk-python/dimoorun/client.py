from __future__ import annotations

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
        tenant_id: int | None = None,
        project_id: int | None = None,
        environment: str | None = None,
        actor_id: str | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._tenant_id = tenant_id
        self._project_id = project_id
        self._environment = environment
        self._actor_id = actor_id
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> DimooRun:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def validate_package(
        self,
        *,
        package_uri: str,
        framework: str,
        adapter: str,
        entrypoint: str,
        manifest: dict[str, Any] | None = None,
        required_secret_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._request_object(
            "POST",
            "/v1/packages/validate",
            json={
                "package_uri": package_uri,
                "framework": framework,
                "adapter": adapter,
                "entrypoint": entrypoint,
                "manifest": manifest or {},
                "required_secret_refs": required_secret_refs or [],
            },
        )

    def create_agent(
        self,
        *,
        name: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        return self._request_object(
            "POST",
            "/v1/agents",
            json={"name": name, "description": description},
        )

    def list_agents(self) -> list[dict[str, Any]]:
        return self._request_list("GET", "/v1/agents")

    def create_agent_version(
        self,
        *,
        agent_id: int | str,
        version: str,
        package_uri: str,
        framework: str,
        adapter: str,
        entrypoint: str,
        capabilities: dict[str, Any] | None = None,
        manifest: dict[str, Any] | None = None,
        status: str = "draft",
    ) -> dict[str, Any]:
        return self._request_object(
            "POST",
            f"/v1/agents/{agent_id}/versions",
            json={
                "version": version,
                "package_uri": package_uri,
                "framework": framework,
                "adapter": adapter,
                "entrypoint": entrypoint,
                "capabilities": capabilities or {},
                "manifest": manifest or {},
                "status": status,
            },
        )

    def create_deployment(
        self,
        *,
        agent_id: int | str,
        agent_version_id: int | str,
        environment: str,
        desired_status: str = "draft",
        replicas: int = 1,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request_object(
            "POST",
            "/v1/deployments",
            json={
                "agent_id": agent_id,
                "agent_version_id": agent_version_id,
                "environment": environment,
                "desired_status": desired_status,
                "replicas": replicas,
                "config": config or {},
            },
        )

    def list_deployments(self) -> list[dict[str, Any]]:
        return self._request_list("GET", "/v1/deployments")

    def create_run(
        self,
        *,
        agent_id: int | str,
        input: dict[str, Any],
        idempotency_key: str | None = None,
        version: str | None = None,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"input": input}
        if version is not None:
            payload["version"] = version
        if thread_id is not None:
            payload["thread_id"] = thread_id
        return self._request_object(
            "POST",
            f"/v1/agents/{agent_id}/tasks",
            json=payload,
            headers={"Idempotency-Key": idempotency_key or f"sdk-{uuid4().hex}"},
        )

    def submit_deployment_task(
        self,
        *,
        deployment_id: int | str,
        input: dict[str, Any],
        idempotency_key: str | None = None,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"input": input}
        if thread_id is not None:
            payload["thread_id"] = thread_id
        return self._request_object(
            "POST",
            f"/v1/deployments/{deployment_id}/tasks",
            json=payload,
            headers={"Idempotency-Key": idempotency_key or f"sdk-{uuid4().hex}"},
        )

    def get_run(self, run_id: int | str) -> dict[str, Any]:
        return self._request_object("GET", f"/v1/runs/{run_id}")

    def list_runs(self) -> list[dict[str, Any]]:
        return self._request_list("GET", "/v1/runs")

    def list_run_events(self, run_id: int | str) -> list[dict[str, Any]]:
        return self._request_list("GET", f"/v1/runs/{run_id}/events")

    def get_task(self, task_id: int | str) -> dict[str, Any]:
        return self._request_object("GET", f"/v1/tasks/{task_id}")

    def replay_run(
        self,
        run_id: int | str,
        *,
        agent_version_id: int | None = None,
    ) -> dict[str, Any]:
        payload = {"agent_version_id": agent_version_id} if agent_version_id is not None else {}
        return self._request_object(
            "POST",
            f"/v1/runs/{run_id}/replay",
            json=payload,
        )

    def _default_headers(self) -> dict[str, str]:
        headers = {"X-Request-Id": f"req_sdk_{uuid4().hex}"}
        if self._tenant_id is not None:
            headers["X-Tenant-Id"] = str(self._tenant_id)
        if self._project_id is not None:
            headers["X-Project-Id"] = str(self._project_id)
        if self._environment is not None:
            headers["X-Environment"] = self._environment
        if self._actor_id is not None:
            headers["X-Actor-Id"] = self._actor_id
        return headers

    def _request_object(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload = self._request_raw(method, path, json=json, headers=headers)
        return self._ensure_json_object(payload)

    def _request_list(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        payload = self._request_raw(method, path, json=json, headers=headers)
        if not isinstance(payload, list):
            self._raise_invalid_response("Expected a JSON array response.")
        return [self._ensure_json_object(item) for item in payload]

    def _request_raw(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        response = self._client.request(
            method,
            path,
            json=json,
            headers=self._default_headers() | (headers or {}),
        )
        if response.is_error:
            self._raise_api_error(response)
        return response.json()

    def _ensure_json_object(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            self._raise_invalid_response("Expected a JSON object response.")
        return dict(payload)

    def _raise_invalid_response(self, message: str) -> None:
        raise DimooRunAPIError(
            error_code="invalid_response",
            message=message,
            request_id=None,
            details={},
        )

    def _raise_api_error(self, response: httpx.Response) -> None:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        raise DimooRunAPIError(
            error_code=str(payload.get("error_code", "unknown")),
            message=str(payload.get("message", response.text)),
            request_id=payload.get("request_id"),
            details=dict(payload.get("details") or {}),
        )
