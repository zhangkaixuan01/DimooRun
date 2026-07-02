from __future__ import annotations

import argparse
import json
import os
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from time import sleep
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

import httpx
import yaml

from dimoo_run.cli.compose import run_compose
from dimoo_run.cli.dev import run_dev
from dimoo_run.config.project import validate_project_workspace, write_default_workspace
from dimoo_run.core.config import Settings
from dimoo_run.core.startup_checks import validate_production_settings
from dimoo_run.migration.aegra import migrate_aegra_project
from dimoo_run.migration.langgraph import migrate_langgraph_project
from dimoo_run.migration.langgraph_platform import migrate_langgraph_platform_project
from dimoo_run.worker.loop import WorkerLoop

LANGCHAIN_VERSION_MATRIX = {
    "langchain": "1.3.1",
    "langchain-core": "1.4.0",
    "langgraph": "1.2.1",
    "deepagents": "0.6.3",
    "langsmith": "0.8.5",
}
TERMINAL_RUN_STATUSES = {"succeeded", "failed", "cancelled", "timeout"}
RUN_SUBCOMMANDS = {"watch", "replay", "triage"}
DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_CONSOLE_URL = "http://127.0.0.1:8080"
DEFAULT_API_KEY = "dev-local-key"
DEFAULT_TENANT_ID = 1
DEFAULT_PROJECT_ID = 1
DEFAULT_ENVIRONMENT = "local"


class CLIAPIError(RuntimeError):
    pass


class NativeAPIClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        tenant_id: int,
        project_id: int,
        environment: str | None = None,
        actor_id: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._tenant_id = tenant_id
        self._project_id = project_id
        self._environment = environment
        self._actor_id = actor_id
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=30.0,
        )

    def close(self) -> None:
        self._client.close()

    def validate_package(
        self,
        *,
        package_uri: str,
        framework: str,
        adapter: str,
        entrypoint: str,
        manifest: dict[str, Any],
        required_secret_refs: list[str],
    ) -> dict[str, Any]:
        return self._request_object(
            "POST",
            "/v1/packages/validate",
            {
                "package_uri": package_uri,
                "framework": framework,
                "adapter": adapter,
                "entrypoint": entrypoint,
                "manifest": manifest,
                "required_secret_refs": required_secret_refs,
            },
        )

    def create_agent(self, *, name: str, description: str | None) -> dict[str, Any]:
        return self._request_object(
            "POST",
            "/v1/agents",
            {"name": name, "description": description},
        )

    def list_agents(self) -> list[dict[str, Any]]:
        return self._request_list("GET", "/v1/agents", None)

    def create_agent_version(
        self,
        *,
        agent_id: int,
        version: str,
        package_uri: str,
        framework: str,
        adapter: str,
        entrypoint: str,
        manifest: dict[str, Any],
        capabilities: dict[str, Any],
    ) -> dict[str, Any]:
        return self._request_object(
            "POST",
            f"/v1/agents/{agent_id}/versions",
            {
                "version": version,
                "package_uri": package_uri,
                "framework": framework,
                "adapter": adapter,
                "entrypoint": entrypoint,
                "manifest": manifest,
                "capabilities": capabilities,
                "status": "ready",
            },
        )

    def list_agent_versions(self, agent_id: int) -> list[dict[str, Any]]:
        return self._request_list("GET", f"/v1/agents/{agent_id}/versions", None)

    def create_deployment(
        self,
        *,
        agent_id: int,
        agent_version_id: int,
        environment: str,
        desired_status: str,
        replicas: int,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        return self._request_object(
            "POST",
            "/v1/deployments",
            {
                "agent_id": agent_id,
                "agent_version_id": agent_version_id,
                "environment": environment,
                "desired_status": desired_status,
                "replicas": replicas,
                "config": config,
            },
        )

    def list_deployments(self) -> list[dict[str, Any]]:
        return self._request_list("GET", "/v1/deployments", None)

    def submit_deployment_task(
        self,
        *,
        deployment_id: int,
        input_data: dict[str, Any],
        thread_id: str | None,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"input": input_data}
        if thread_id is not None:
            payload["thread_id"] = thread_id
        return self._request_object(
            "POST",
            f"/v1/deployments/{deployment_id}/tasks",
            payload,
            extra_headers={"Idempotency-Key": idempotency_key or f"cli-{uuid4().hex}"},
        )

    def get_run(self, run_id: int) -> dict[str, Any]:
        return self._request_object("GET", f"/v1/runs/{run_id}", None)

    def list_run_events(self, run_id: int) -> list[dict[str, Any]]:
        return self._request_list("GET", f"/v1/runs/{run_id}/events", None)

    def get_run_integration_evidence(self, run_id: int) -> dict[str, Any]:
        return self._request_object("GET", f"/v1/runs/{run_id}/integration-evidence", None)

    def replay_run(self, run_id: int, *, agent_version_id: int | None) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if agent_version_id is not None:
            payload["agent_version_id"] = agent_version_id
        return self._request_object("POST", f"/v1/runs/{run_id}/replay", payload)

    def rollback_deployment(
        self,
        *,
        deployment_id: int,
        expected_current_version_id: int,
        rollback_agent_version_id: int | None,
        rollback_reason: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "expected_current_version_id": expected_current_version_id,
            "rollback_reason": rollback_reason,
        }
        if rollback_agent_version_id is not None:
            payload["rollback_agent_version_id"] = rollback_agent_version_id
        return self._request_object("POST", f"/v1/deployments/{deployment_id}/rollback", payload)

    def decide_human_task(
        self,
        *,
        task_id: int,
        decision: str,
        comment: str,
    ) -> dict[str, Any]:
        payload = {
            "decision_payload": {
                "source": "cli",
                "comment": comment,
                "decided_by": "cli",
            }
        }
        return self._request_object("POST", f"/v1/human-tasks/{task_id}/{decision}", payload)

    def _request_object(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        body = self._request_raw(method, path, payload, extra_headers=extra_headers)
        return _ensure_object(body)

    def _request_list(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        body = self._request_raw(method, path, payload, extra_headers=extra_headers)
        if not isinstance(body, list):
            raise CLIAPIError("Expected a JSON array response.")
        return [_ensure_object(item) for item in body]

    def _request_raw(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        response = self._client.request(
            method,
            path,
            json=payload,
            headers=self._headers() | (extra_headers or {}),
        )
        if response.is_error:
            raise CLIAPIError(_format_api_error(response))
        return response.json()

    def _headers(self) -> dict[str, str]:
        headers = {
            "X-Tenant-Id": str(self._tenant_id),
            "X-Project-Id": str(self._project_id),
            "X-Request-Id": f"req_cli_{uuid4().hex}",
        }
        if self._environment is not None:
            headers["X-Environment"] = self._environment
        if self._actor_id is not None:
            headers["X-Actor-Id"] = self._actor_id
        return headers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dimoorun")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--path", default=".")
    init_parser.add_argument("--name", default="support-agent")

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--path", default=".")

    publish_parser = subparsers.add_parser("publish")
    _add_product_api_connection_args(publish_parser)
    publish_parser.add_argument("path")
    publish_parser.add_argument("--name")
    publish_parser.add_argument("--description")
    publish_parser.add_argument("--version")
    publish_parser.add_argument("--package-uri")
    publish_parser.add_argument("--framework")
    publish_parser.add_argument("--adapter")
    publish_parser.add_argument("--entrypoint")
    publish_parser.add_argument("--manifest-file")
    publish_parser.add_argument("--capabilities-file")
    publish_parser.add_argument("--secret-ref", action="append", default=[])

    deploy_parser = subparsers.add_parser("deploy")
    _add_product_api_connection_args(deploy_parser)
    deploy_parser.add_argument("agent_name")
    deploy_parser.add_argument("--version")
    deploy_parser.add_argument("--env", dest="target_environment", default=DEFAULT_ENVIRONMENT)
    deploy_parser.add_argument("--replicas", type=int, default=1)
    deploy_parser.add_argument("--config-file")

    quick_run_parser = subparsers.add_parser(
        "quick-run",
        help=argparse.SUPPRESS,
        prog="dimoorun run",
    )
    _add_product_api_connection_args(quick_run_parser)
    quick_run_parser.add_argument("agent_name")
    quick_run_parser.add_argument("--env", dest="target_environment", default=DEFAULT_ENVIRONMENT)
    quick_run_parser.add_argument("--input-json")
    quick_run_parser.add_argument("--input-file")
    quick_run_parser.add_argument("--thread-id")
    quick_run_parser.add_argument("--idempotency-key")
    quick_run_parser.add_argument("--watch", action="store_true")
    quick_run_parser.add_argument("--poll-interval", type=float, default=1.0)
    quick_run_parser.add_argument("--max-polls", type=int, default=30)
    quick_run_parser.add_argument("--show-events", action="store_true")

    open_parser = subparsers.add_parser("open")
    open_parser.add_argument(
        "--console-url",
        default=os.getenv("DIMOORUN_CONSOLE_URL", DEFAULT_CONSOLE_URL),
    )
    open_parser.add_argument("--run-id", type=int)
    open_parser.add_argument("--deployment-id", type=int)
    open_parser.add_argument("--agent-id", type=int)

    demo_parser = subparsers.add_parser("demo")
    demo_subparsers = demo_parser.add_subparsers(dest="demo_command", required=True)
    demo_seed_parser = demo_subparsers.add_parser("seed")
    _add_product_api_connection_args(demo_seed_parser)
    demo_seed_parser.add_argument("--path", default="examples/langgraph/support-agent")
    demo_seed_parser.add_argument("--name", default="support-agent")
    demo_seed_parser.add_argument("--version")
    demo_seed_parser.add_argument("--env", dest="target_environment", default=DEFAULT_ENVIRONMENT)
    demo_seed_parser.add_argument(
        "--input-json",
        default='{"message":"customer asks for refund and account deletion"}',
    )
    demo_seed_parser.add_argument("--thread-id", default="p0a-demo-seed")
    demo_seed_parser.add_argument("--watch", action="store_true")
    demo_seed_parser.add_argument(
        "--console-url",
        default=os.getenv("DIMOORUN_CONSOLE_URL", DEFAULT_CONSOLE_URL),
    )

    doctor_parser = subparsers.add_parser("doctor")
    doctor_subparsers = doctor_parser.add_subparsers(dest="doctor_command")
    doctor_subparsers.add_parser("production")
    dev_parser = subparsers.add_parser("dev")
    dev_parser.add_argument("--dry-run", action="store_true")
    worker_parser = subparsers.add_parser("worker")
    worker_parser.add_argument("--once", action="store_true")
    for command_name in ("up", "down", "logs"):
        compose_parser = subparsers.add_parser(command_name)
        compose_parser.add_argument("--dry-run", action="store_true")
    migrate_parser = subparsers.add_parser("migrate")
    migrate_subparsers = migrate_parser.add_subparsers(dest="migration_source", required=True)
    for source_name in ("langgraph", "aegra", "langgraph-platform"):
        source_parser = migrate_subparsers.add_parser(source_name)
        source_parser.add_argument("source")
        source_parser.add_argument("--output", required=True)
        source_parser.add_argument("--name", required=True)

    package_parser = subparsers.add_parser("package")
    package_subparsers = package_parser.add_subparsers(dest="package_command", required=True)
    package_validate_parser = package_subparsers.add_parser("validate")
    _add_api_connection_args(package_validate_parser)
    package_validate_parser.add_argument("--package-uri", required=True)
    package_validate_parser.add_argument("--framework", required=True)
    package_validate_parser.add_argument("--adapter", required=True)
    package_validate_parser.add_argument("--entrypoint", required=True)
    package_validate_parser.add_argument("--manifest-file")
    package_validate_parser.add_argument("--secret-ref", action="append", default=[])

    agent_parser = subparsers.add_parser("agent")
    agent_subparsers = agent_parser.add_subparsers(dest="agent_command", required=True)
    agent_publish_parser = agent_subparsers.add_parser("publish")
    _add_api_connection_args(agent_publish_parser)
    agent_publish_parser.add_argument("--agent-id", type=int)
    agent_publish_parser.add_argument("--name")
    agent_publish_parser.add_argument("--description")
    agent_publish_parser.add_argument("--version", required=True)
    agent_publish_parser.add_argument("--package-uri", required=True)
    agent_publish_parser.add_argument("--framework", required=True)
    agent_publish_parser.add_argument("--adapter", required=True)
    agent_publish_parser.add_argument("--entrypoint", required=True)
    agent_publish_parser.add_argument("--manifest-file")
    agent_publish_parser.add_argument("--capabilities-file")
    agent_publish_parser.add_argument("--secret-ref", action="append", default=[])

    deployment_parser = subparsers.add_parser("deployment")
    deployment_subparsers = deployment_parser.add_subparsers(
        dest="deployment_command",
        required=True,
    )
    deployment_create_parser = deployment_subparsers.add_parser("create")
    _add_api_connection_args(deployment_create_parser)
    deployment_create_parser.add_argument("--agent-id", type=int, required=True)
    deployment_create_parser.add_argument("--agent-version-id", type=int, required=True)
    deployment_create_parser.add_argument("--target-environment", required=True)
    deployment_create_parser.add_argument("--desired-status", default="draft")
    deployment_create_parser.add_argument("--replicas", type=int, default=1)
    deployment_create_parser.add_argument("--config-file")
    deployment_rollback_parser = deployment_subparsers.add_parser("rollback")
    _add_api_connection_args(deployment_rollback_parser)
    deployment_rollback_parser.add_argument("--deployment-id", type=int, required=True)
    deployment_rollback_parser.add_argument("--expected-current-version-id", type=int, required=True)
    deployment_rollback_parser.add_argument("--rollback-agent-version-id", type=int)
    deployment_rollback_parser.add_argument("--rollback-reason", required=True)
    deployment_task_parser = deployment_subparsers.add_parser("task")
    deployment_task_subparsers = deployment_task_parser.add_subparsers(
        dest="deployment_task_command",
        required=True,
    )
    deployment_task_submit_parser = deployment_task_subparsers.add_parser("submit")
    _add_api_connection_args(deployment_task_submit_parser)
    deployment_task_submit_parser.add_argument("--deployment-id", type=int, required=True)
    deployment_task_submit_parser.add_argument("--input-json")
    deployment_task_submit_parser.add_argument("--input-file")
    deployment_task_submit_parser.add_argument("--thread-id")
    deployment_task_submit_parser.add_argument("--idempotency-key")

    run_parser = subparsers.add_parser("run")
    run_subparsers = run_parser.add_subparsers(dest="run_command", required=True)
    run_watch_parser = run_subparsers.add_parser("watch")
    _add_api_connection_args(run_watch_parser)
    run_watch_parser.add_argument("--run-id", type=int, required=True)
    run_watch_parser.add_argument("--poll-interval", type=float, default=1.0)
    run_watch_parser.add_argument("--max-polls", type=int, default=30)
    run_watch_parser.add_argument("--show-events", action="store_true")
    run_replay_parser = run_subparsers.add_parser("replay")
    _add_api_connection_args(run_replay_parser)
    run_replay_parser.add_argument("--run-id", type=int, required=True)
    run_replay_parser.add_argument("--agent-version-id", type=int)
    run_triage_parser = run_subparsers.add_parser("triage")
    _add_api_connection_args(run_triage_parser)
    run_triage_parser.add_argument("--run-id", type=int, required=True)
    run_triage_parser.add_argument("--console-url", default=DEFAULT_CONSOLE_URL)
    human_task_parser = subparsers.add_parser("human-task")
    human_task_subparsers = human_task_parser.add_subparsers(
        dest="human_task_command",
        required=True,
    )
    human_task_decide_parser = human_task_subparsers.add_parser("decide")
    _add_api_connection_args(human_task_decide_parser)
    human_task_decide_parser.add_argument("--task-id", type=int, required=True)
    human_task_decide_parser.add_argument("--decision", choices=["approve", "reject"], required=True)
    human_task_decide_parser.add_argument("--comment", required=True)
    return parser


def _add_api_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument("--environment")
    parser.add_argument("--actor-id")


def _add_product_api_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", default=os.getenv("DIMOORUN_API_BASE_URL", DEFAULT_API_BASE_URL))
    parser.add_argument("--api-key", default=os.getenv("DIMOORUN_API_KEY", DEFAULT_API_KEY))
    parser.add_argument("--tenant-id", type=int, default=DEFAULT_TENANT_ID)
    parser.add_argument("--project-id", type=int, default=DEFAULT_PROJECT_ID)
    parser.add_argument("--environment", default=DEFAULT_ENVIRONMENT)
    parser.add_argument("--actor-id")


def _installed_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return "not installed"


def _ensure_object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CLIAPIError("Expected a JSON object response.")
    return dict(value)


def _format_api_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    error_code = payload.get("error_code", "unknown")
    message = payload.get("message", response.text)
    return f"{error_code}: {message}"


def _load_json_file(path: str | None) -> dict[str, Any]:
    if path is None:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return _ensure_object(data)


def _load_json_or_yaml_file(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _ensure_object(data or {})


def _load_manifest_from_agent_path(path: Path, explicit_manifest: str | None) -> dict[str, Any]:
    if explicit_manifest is not None:
        return _load_json_or_yaml_file(Path(explicit_manifest))
    for name in ("manifest.json", "manifest.yaml", "manifest.yml"):
        candidate = path / name
        if candidate.exists():
            return _load_json_or_yaml_file(candidate)
    raise CLIAPIError(
        "manifest_not_found: expected manifest.json, manifest.yaml, or manifest.yml "
        f"under {path}"
    )


def _default_package_uri(path: Path) -> str:
    if path.is_absolute():
        return path.as_uri()
    return f"file:///workspace/{path.as_posix()}"


def _manifest_runtime(manifest: dict[str, Any]) -> dict[str, Any]:
    runtime = manifest.get("runtime", {})
    if not isinstance(runtime, dict):
        raise CLIAPIError("invalid_manifest: manifest.runtime must be an object.")
    return runtime


def _required_secret_refs(manifest: dict[str, Any], explicit_refs: list[str]) -> list[str]:
    refs = list(explicit_refs)
    required = manifest.get("required_secrets", [])
    if isinstance(required, list):
        refs.extend(str(item) for item in required)
    secrets = manifest.get("secrets", [])
    if isinstance(secrets, list):
        for item in secrets:
            if isinstance(item, dict) and item.get("ref") is not None:
                refs.append(str(item["ref"]))
    return sorted({ref for ref in refs if ref})


def _load_input_payload(*, input_json: str | None, input_file: str | None) -> dict[str, Any]:
    if input_json is not None and input_file is not None:
        raise CLIAPIError("Provide either --input-json or --input-file, not both.")
    if input_file is not None:
        return _load_json_file(input_file)
    if input_json is None:
        return {}
    data = json.loads(input_json)
    return _ensure_object(data)


def _make_api_client(args: argparse.Namespace) -> NativeAPIClient:
    return NativeAPIClient(
        base_url=args.base_url,
        api_key=args.api_key,
        tenant_id=args.tenant_id,
        project_id=args.project_id,
        environment=getattr(args, "environment", None),
        actor_id=getattr(args, "actor_id", None),
    )


def _find_agent_by_name(client: NativeAPIClient, name: str) -> dict[str, Any] | None:
    for agent in client.list_agents():
        if agent.get("name") == name and agent.get("status", "active") != "archived":
            return agent
    return None


def _select_ready_version(
    client: NativeAPIClient,
    *,
    agent_id: int,
    version: str | None,
) -> dict[str, Any]:
    versions = client.list_agent_versions(agent_id)
    ready_versions = [item for item in versions if item.get("status") == "ready"]
    if version is not None:
        for item in ready_versions:
            if item.get("version") == version:
                return item
        raise CLIAPIError(
            f"agent_version_not_ready: agent {agent_id} has no ready version {version!r}."
        )
    if not ready_versions:
        raise CLIAPIError(f"agent_version_not_ready: agent {agent_id} has no ready versions.")
    return ready_versions[-1]


def _find_deployment(
    client: NativeAPIClient,
    *,
    agent_id: int,
    environment: str,
) -> dict[str, Any] | None:
    for deployment in client.list_deployments():
        if deployment.get("agent_id") == agent_id and deployment.get("environment") == environment:
            return deployment
    return None


def _console_url(path: str, *, base_url: str = DEFAULT_CONSOLE_URL) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _print_productized_result(kind: str, payload: dict[str, Any], *, console_path: str) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    print(f"next: {_console_url(console_path)}")


def _publish_agent_path(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).as_posix()
    agent_path = Path(path)
    manifest = _load_manifest_from_agent_path(agent_path, args.manifest_file)
    runtime = _manifest_runtime(manifest)
    capabilities = _load_json_file(args.capabilities_file) if args.capabilities_file else dict(
        manifest.get("capabilities", {})
        if isinstance(manifest.get("capabilities", {}), dict)
        else {}
    )
    name = args.name or str(manifest.get("name") or agent_path.name)
    version = args.version or str(manifest.get("version") or "0.1.0")
    framework = args.framework or str(runtime.get("framework") or "")
    adapter = args.adapter or str(runtime.get("adapter") or framework)
    entrypoint = args.entrypoint or str(runtime.get("entrypoint") or "")
    if not framework or not adapter or not entrypoint:
        raise CLIAPIError(
            "invalid_manifest: runtime.framework, runtime.adapter, and runtime.entrypoint "
            "are required."
        )
    package_uri = args.package_uri or _default_package_uri(agent_path)
    client = _make_api_client(args)
    try:
        validation = client.validate_package(
            package_uri=package_uri,
            framework=framework,
            adapter=adapter,
            entrypoint=entrypoint,
            manifest=manifest,
            required_secret_refs=_required_secret_refs(manifest, list(args.secret_ref)),
        )
        token = validation.get("validation_token")
        if not validation.get("ready") or not isinstance(token, str):
            raise CLIAPIError("Package validation did not return a ready validation token.")
        manifest_with_token = dict(manifest)
        manifest_with_token["validation_token"] = token
        agent = _find_agent_by_name(client, name)
        if agent is None:
            agent = client.create_agent(name=name, description=args.description)
        agent_id = int(agent["id"])
        existing_versions = client.list_agent_versions(agent_id)
        for item in existing_versions:
            if item.get("version") == version and item.get("status") == "ready":
                return {
                    "agent": agent,
                    "version": item,
                    "validation": validation,
                    "reused": True,
                }
        version_payload = client.create_agent_version(
            agent_id=agent_id,
            version=version,
            package_uri=package_uri,
            framework=framework,
            adapter=adapter,
            entrypoint=entrypoint,
            manifest=manifest_with_token,
            capabilities=capabilities,
        )
        return {
            "agent": agent,
            "version": version_payload,
            "validation": validation,
            "reused": False,
        }
    finally:
        client.close()


def _run_product_publish(args: argparse.Namespace) -> int:
    result = _publish_agent_path(args)
    agent_id = int(result["agent"]["id"])
    _print_productized_result(
        "publish",
        {
            "agent_id": agent_id,
            "agent_name": result["agent"].get("name"),
            "agent_version_id": result["version"].get("id"),
            "version": result["version"].get("version"),
            "status": result["version"].get("status"),
            "validation_token": result["validation"].get("validation_token"),
            "reused": result["reused"],
        },
        console_path=f"/agents?agent_id={agent_id}",
    )
    print(f"next command: dimoorun deploy {result['agent'].get('name')} --env {args.environment}")
    return 0


def _run_product_deploy(args: argparse.Namespace) -> int:
    client = _make_api_client(args)
    try:
        agent = _find_agent_by_name(client, args.agent_name)
        if agent is None:
            raise CLIAPIError(f"agent_not_found: {args.agent_name!r} is not published.")
        version = _select_ready_version(
            client,
            agent_id=int(agent["id"]),
            version=args.version,
        )
        existing = _find_deployment(
            client,
            agent_id=int(agent["id"]),
            environment=args.target_environment,
        )
        if existing is not None:
            deployment = existing
            reused = True
        else:
            deployment = client.create_deployment(
                agent_id=int(agent["id"]),
                agent_version_id=int(version["id"]),
                environment=args.target_environment,
                desired_status="active",
                replicas=args.replicas,
                config=_load_json_file(args.config_file),
            )
            reused = False
    finally:
        client.close()
    deployment_id = int(deployment["id"])
    _print_productized_result(
        "deploy",
        {
            "agent_id": agent["id"],
            "agent_name": agent.get("name"),
            "agent_version_id": version["id"],
            "deployment_id": deployment_id,
            "environment": deployment.get("environment"),
            "desired_status": deployment.get("desired_status"),
            "reused": reused,
        },
        console_path=f"/deployments/{deployment_id}",
    )
    print(
        "next command: "
        f"dimoorun run {args.agent_name} --env {args.target_environment} "
        '--input-json "{\\"message\\":\\"hello from DimooRun\\"}" --watch'
    )
    return 0


def _run_product_run(args: argparse.Namespace) -> int:
    client = _make_api_client(args)
    try:
        agent = _find_agent_by_name(client, args.agent_name)
        if agent is None:
            raise CLIAPIError(f"agent_not_found: {args.agent_name!r} is not published.")
        deployment = _find_deployment(
            client,
            agent_id=int(agent["id"]),
            environment=args.target_environment,
        )
        if deployment is None:
            raise CLIAPIError(
                "deployment_not_found: "
                f"{args.agent_name!r} has no deployment in {args.target_environment!r}."
            )
        result = client.submit_deployment_task(
            deployment_id=int(deployment["id"]),
            input_data=_load_input_payload(input_json=args.input_json, input_file=args.input_file),
            thread_id=args.thread_id,
            idempotency_key=args.idempotency_key,
        )
        run_id = int(result["run_id"])
        _print_productized_result(
            "run",
            {
                "agent_id": agent["id"],
                "agent_name": agent.get("name"),
                "deployment_id": deployment["id"],
                "run_id": run_id,
                "task_id": result.get("task_id"),
                "status": result.get("status"),
            },
            console_path=f"/runs/{run_id}",
        )
        if args.watch:
            watch_args = argparse.Namespace(
                **vars(args),
                run_id=run_id,
            )
            return _watch_with_client(client, watch_args)
        return 0
    finally:
        client.close()


def _run_open(args: argparse.Namespace) -> int:
    path = "/dashboard"
    if args.run_id is not None:
        path = f"/runs/{args.run_id}"
    elif args.deployment_id is not None:
        path = f"/deployments/{args.deployment_id}"
    elif args.agent_id is not None:
        path = f"/agents?agent_id={args.agent_id}"
    print(_console_url(path, base_url=args.console_url))
    return 0


def _run_demo_seed(args: argparse.Namespace) -> int:
    publish_namespace = vars(args).copy()
    publish_namespace.update(
        {
            "path": args.path,
            "manifest_file": None,
            "capabilities_file": None,
            "package_uri": None,
            "framework": None,
            "adapter": None,
            "entrypoint": None,
            "description": "P0-A first-run demo seed",
            "secret_ref": [],
        }
    )
    publish_args = argparse.Namespace(
        **publish_namespace,
    )
    publish_result = _publish_agent_path(publish_args)
    client = _make_api_client(args)
    try:
        deployment = _find_deployment(
            client,
            agent_id=int(publish_result["agent"]["id"]),
            environment=args.target_environment,
        )
        if deployment is None:
            deployment = client.create_deployment(
                agent_id=int(publish_result["agent"]["id"]),
                agent_version_id=int(publish_result["version"]["id"]),
                environment=args.target_environment,
                desired_status="active",
                replicas=1,
                config={},
            )
        run = client.submit_deployment_task(
            deployment_id=int(deployment["id"]),
            input_data=_load_input_payload(input_json=args.input_json, input_file=None),
            thread_id=args.thread_id,
            idempotency_key=f"demo-seed-{uuid4().hex}",
        )
        payload = {
            "agent_id": publish_result["agent"]["id"],
            "agent_name": publish_result["agent"]["name"],
            "agent_version_id": publish_result["version"]["id"],
            "deployment_id": deployment["id"],
            "environment": deployment["environment"],
            "run_id": run["run_id"],
            "task_id": run["task_id"],
            "console": {
                "dashboard": _console_url("/dashboard", base_url=args.console_url),
                "deployment": _console_url(
                    f"/deployments/{deployment['id']}",
                    base_url=args.console_url,
                ),
                "run": _console_url(f"/runs/{run['run_id']}", base_url=args.console_url),
            },
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        if args.watch:
            watch_args = argparse.Namespace(
                **vars(args),
                run_id=int(run["run_id"]),
                poll_interval=1.0,
                max_polls=30,
                show_events=True,
            )
            return _watch_with_client(client, watch_args)
        return 0
    finally:
        client.close()


def _run_package_validate(args: argparse.Namespace) -> int:
    client = _make_api_client(args)
    try:
        result = client.validate_package(
            package_uri=args.package_uri,
            framework=args.framework,
            adapter=args.adapter,
            entrypoint=args.entrypoint,
            manifest=_load_json_file(args.manifest_file),
            required_secret_refs=list(args.secret_ref),
        )
    finally:
        client.close()
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def _run_agent_publish(args: argparse.Namespace) -> int:
    if args.agent_id is None and not args.name:
        raise CLIAPIError("agent publish requires --agent-id or --name.")
    manifest = _load_json_file(args.manifest_file)
    capabilities = _load_json_file(args.capabilities_file)
    client = _make_api_client(args)
    try:
        validation = client.validate_package(
            package_uri=args.package_uri,
            framework=args.framework,
            adapter=args.adapter,
            entrypoint=args.entrypoint,
            manifest=manifest,
            required_secret_refs=list(args.secret_ref),
        )
        token = validation.get("validation_token")
        if not validation.get("ready") or not isinstance(token, str):
            raise CLIAPIError("Package validation did not return a ready validation token.")
        manifest_with_token = dict(manifest)
        manifest_with_token["validation_token"] = token
        if args.agent_id is None:
            agent = client.create_agent(name=args.name, description=args.description)
            agent_id = int(agent["id"])
        else:
            agent_id = int(args.agent_id)
        version_payload = client.create_agent_version(
            agent_id=agent_id,
            version=args.version,
            package_uri=args.package_uri,
            framework=args.framework,
            adapter=args.adapter,
            entrypoint=args.entrypoint,
            manifest=manifest_with_token,
            capabilities=capabilities,
        )
    finally:
        client.close()
    print(json.dumps(version_payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def _run_deployment_task_submit(args: argparse.Namespace) -> int:
    client = _make_api_client(args)
    try:
        result = client.submit_deployment_task(
            deployment_id=args.deployment_id,
            input_data=_load_input_payload(input_json=args.input_json, input_file=args.input_file),
            thread_id=args.thread_id,
            idempotency_key=args.idempotency_key,
        )
    finally:
        client.close()
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def _run_deployment_create(args: argparse.Namespace) -> int:
    client = _make_api_client(args)
    try:
        result = client.create_deployment(
            agent_id=args.agent_id,
            agent_version_id=args.agent_version_id,
            environment=args.target_environment,
            desired_status=args.desired_status,
            replicas=args.replicas,
            config=_load_json_file(args.config_file),
        )
    finally:
        client.close()
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def _run_deployment_rollback(args: argparse.Namespace) -> int:
    client = _make_api_client(args)
    try:
        result = client.rollback_deployment(
            deployment_id=args.deployment_id,
            expected_current_version_id=args.expected_current_version_id,
            rollback_agent_version_id=args.rollback_agent_version_id,
            rollback_reason=args.rollback_reason,
        )
    finally:
        client.close()
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def _run_watch(args: argparse.Namespace) -> int:
    client = _make_api_client(args)
    try:
        return _watch_with_client(client, args)
    finally:
        client.close()


def _watch_with_client(client: NativeAPIClient, args: argparse.Namespace) -> int:
    seen_sequences: set[int] = set()
    for _ in range(args.max_polls):
        run = client.get_run(args.run_id)
        print(
            json.dumps(
                {
                    "id": run.get("id"),
                    "status": run.get("status"),
                    "started_at": run.get("started_at"),
                    "finished_at": run.get("finished_at"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        if args.show_events:
            for event in client.list_run_events(args.run_id):
                sequence = int(event.get("sequence", 0))
                if sequence in seen_sequences:
                    continue
                seen_sequences.add(sequence)
                print(json.dumps(event, ensure_ascii=False, sort_keys=True))
        if str(run.get("status")) in TERMINAL_RUN_STATUSES:
            return 0
        sleep(args.poll_interval)
    raise CLIAPIError(
        "run_watch_timeout: Run "
        f"{args.run_id} did not reach a terminal state after {args.max_polls} polls."
    )


def _run_replay(args: argparse.Namespace) -> int:
    client = _make_api_client(args)
    try:
        result = client.replay_run(args.run_id, agent_version_id=args.agent_version_id)
    finally:
        client.close()
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def _run_triage(args: argparse.Namespace) -> int:
    client = _make_api_client(args)
    try:
        run = client.get_run(args.run_id)
        events = client.list_run_events(args.run_id)
        integration_evidence = client.get_run_integration_evidence(args.run_id)
    finally:
        client.close()
    deployment_id = _first_int(run, ["deployment_id", "deployment"])
    agent_version_id = _first_int(run, ["agent_version_id", "agent_version"])
    operator_actions: dict[str, str] = {
        "run_detail": _console_url(f"/runs/{args.run_id}", base_url=args.console_url),
        "triage": _console_url(f"/runs/{args.run_id}/triage", base_url=args.console_url),
        "replay": _console_url(
            f"/replay/compare?{urlencode({'source_run_id': args.run_id})}",
            base_url=args.console_url,
        ),
        "approval": _console_url(
            f"/governance/human-tasks?{urlencode({'run_id': args.run_id})}",
            base_url=args.console_url,
        ),
        "audit": _console_url(
            f"/observability/audit-logs?{urlencode({'run_id': args.run_id})}",
            base_url=args.console_url,
        ),
        "integration_evidence": _console_url(
            f"/runs/{args.run_id}#integration-evidence",
            base_url=args.console_url,
        ),
    }
    if deployment_id is not None:
        operator_actions["promotion_rollback"] = _console_url(
            f"/deployments/{deployment_id}?tab=promotion",
            base_url=args.console_url,
        )
    next_commands: dict[str, str] = {
        "replay": f"dimoorun run replay --run-id {args.run_id} --agent-version-id CANDIDATE_VERSION_ID",
        "approval": "dimoorun human-task decide --task-id TASK_ID --decision approve --comment \"approved from triage\"",
    }
    if deployment_id is not None and agent_version_id is not None:
        next_commands["rollback"] = (
            "dimoorun deployment rollback "
            f"--deployment-id {deployment_id} "
            f"--expected-current-version-id {agent_version_id} "
            "--rollback-agent-version-id ROLLBACK_VERSION_ID "
            "--rollback-reason \"rollback from failed run triage\""
        )
    payload = {
        "run": {
            "id": run.get("id"),
            "status": run.get("status"),
            "deployment_id": deployment_id,
            "agent_version_id": agent_version_id,
            "error": run.get("error"),
        },
        "events": events,
        "integration_evidence": integration_evidence,
        "operator_actions": operator_actions,
        "next_commands": next_commands,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def _first_int(source: dict[str, Any], keys: list[str]) -> int | None:
    for key in keys:
        value = source.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _run_human_task_decide(args: argparse.Namespace) -> int:
    client = _make_api_client(args)
    try:
        result = client.decide_human_task(
            task_id=args.task_id,
            decision=args.decision,
            comment=args.comment,
        )
    finally:
        client.close()
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def _normalize_argv(argv: list[str] | None) -> list[str]:
    items = list(sys.argv[1:] if argv is None else argv)
    if len(items) >= 2 and items[0] == "run" and items[1] not in RUN_SUBCOMMANDS:
        return ["quick-run", *items[1:]]
    return items


def run_cli(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(_normalize_argv(argv))
    try:
        return _run_cli(args)
    except CLIAPIError as exc:
        print(str(exc))
        return 1
    except json.JSONDecodeError as exc:
        print(f"invalid_json: {exc}")
        return 1


def _run_cli(args: argparse.Namespace) -> int:
    if args.command == "init":
        write_default_workspace(Path(args.path), name=args.name)
        print(f"Initialized DimooRun workspace at {Path(args.path)}")
        return 0
    if args.command == "validate":
        errors = validate_project_workspace(Path(args.path))
        if errors:
            for error in errors:
                print(error)
            return 1
        print("DimooRun workspace is valid")
        return 0
    if args.command == "publish":
        return _run_product_publish(args)
    if args.command == "deploy":
        return _run_product_deploy(args)
    if args.command == "quick-run":
        return _run_product_run(args)
    if args.command == "open":
        return _run_open(args)
    if args.command == "demo" and args.demo_command == "seed":
        return _run_demo_seed(args)
    if args.command == "doctor":
        if args.doctor_command == "production":
            errors = validate_production_settings(Settings.from_env())
            if errors:
                for error in errors:
                    print(error)
                return 1
            print("Production settings are valid")
            return 0
        print("DimooRun doctor")
        for package_name, expected in LANGCHAIN_VERSION_MATRIX.items():
            print(f"{package_name}=={expected} installed={_installed_version(package_name)}")
        return 0
    if args.command == "dev":
        return run_dev(dry_run=args.dry_run)
    if args.command in {"up", "down", "logs"}:
        return run_compose(args.command, dry_run=args.dry_run).return_code
    if args.command == "worker":
        loop = WorkerLoop()
        if args.once:
            heartbeat = loop.run_once()
            print(f"{heartbeat.worker_id} {heartbeat.status}")
            return 0
        loop.run_forever()
        return 0
    if args.command == "migrate":
        migrations = {
            "langgraph": migrate_langgraph_project,
            "aegra": migrate_aegra_project,
            "langgraph-platform": migrate_langgraph_platform_project,
        }
        report = migrations[args.migration_source](
            Path(args.source),
            Path(args.output),
            project_name=args.name,
        )
        print(f"Migration report written to {report.report_path}")
        return 0
    if args.command == "package" and args.package_command == "validate":
        return _run_package_validate(args)
    if args.command == "agent" and args.agent_command == "publish":
        return _run_agent_publish(args)
    if args.command == "deployment" and args.deployment_command == "create":
        return _run_deployment_create(args)
    if args.command == "deployment" and args.deployment_command == "rollback":
        return _run_deployment_rollback(args)
    if (
        args.command == "deployment"
        and args.deployment_command == "task"
        and args.deployment_task_command == "submit"
    ):
        return _run_deployment_task_submit(args)
    if args.command == "run" and args.run_command == "watch":
        return _run_watch(args)
    if args.command == "run" and args.run_command == "replay":
        return _run_replay(args)
    if args.command == "run" and args.run_command == "triage":
        return _run_triage(args)
    if args.command == "human-task" and args.human_task_command == "decide":
        return _run_human_task_decide(args)

    print(f"{args.command} is registered but not implemented yet")
    return 2


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
