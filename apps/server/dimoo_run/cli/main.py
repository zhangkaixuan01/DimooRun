from __future__ import annotations

import argparse
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from time import sleep
from typing import Any
from uuid import uuid4

import httpx

from dimoo_run.cli.compose import run_compose
from dimoo_run.cli.dev import run_dev
from dimoo_run.config.project import validate_project_workspace, write_default_workspace
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

    def replay_run(self, run_id: int, *, agent_version_id: int | None) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if agent_version_id is not None:
            payload["agent_version_id"] = agent_version_id
        return self._request_object("POST", f"/v1/runs/{run_id}/replay", payload)

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

    subparsers.add_parser("doctor")
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
    return parser


def _add_api_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument("--environment")
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


def _run_watch(args: argparse.Namespace) -> int:
    client = _make_api_client(args)
    seen_sequences: set[int] = set()
    try:
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
    finally:
        client.close()
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


def run_cli(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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
    if args.command == "doctor":
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

    print(f"{args.command} is registered but not implemented yet")
    return 2


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
