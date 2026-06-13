from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml

REQUIRED_VALUES = [
    ("server", "replicas"),
    ("server", "resources"),
    ("worker", "replicas"),
    ("worker", "resources"),
    ("console", "ingress"),
    ("console", "resources"),
    ("postgres", "external"),
    ("redis", "external"),
    ("objectStore", "external"),
    ("secretProvider", "mode"),
    ("sandbox", "mode"),
    ("resources", "defaults"),
    ("autoscaling",),
    ("migrationJob", "enabled"),
    ("networkPolicy", "enabled"),
    ("podDisruptionBudget", "enabled"),
    ("serviceMonitor", "enabled"),
]

REQUIRED_TEMPLATE_SNIPPETS = [
    "kind: Deployment",
    "kind: Service",
    "kind: Ingress",
    "kind: ConfigMap",
    "kind: ServiceAccount",
    "kind: HorizontalPodAutoscaler",
    "kind: Job",
    "kind: NetworkPolicy",
    "kind: PodDisruptionBudget",
    "kind: ServiceMonitor",
    "secretKeyRef",
    "helm.sh/hook: pre-install,pre-upgrade",
]

HELM_RELEASE = "dimoorun-smoke"
HELM_NAMESPACE = "dimoorun-smoke"
HELM_TIMEOUT = "10m"
LIVE_SMOKE_HELM_SET_ARGS = [
    "--set",
    "serviceMonitor.enabled=false",
    "--set",
    "migrationJob.enabled=false",
    "--set",
    "autoscaling.enabled=false",
    "--set",
    "server.replicas=0",
    "--set",
    "worker.replicas=0",
    "--set",
    "console.replicas=0",
]


@dataclass(frozen=True)
class HelmSmokeResult:
    errors: list[str] = field(default_factory=list)
    checked_steps: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


class HelmSmokeRunner(Protocol):
    def run(self, command: list[str], timeout_seconds: int) -> None: ...

    def available(self, executable: str) -> bool: ...


class SubprocessHelmSmokeRunner:
    def run(self, command: list[str], timeout_seconds: int) -> None:
        subprocess.run(command, check=True, timeout=timeout_seconds)

    def available(self, executable: str) -> bool:
        return shutil.which(executable) is not None


def validate_helm_chart(root: Path) -> HelmSmokeResult:
    chart_dir = root / "deploy/helm/dimoorun"
    values_path = chart_dir / "values.yaml"
    templates_dir = chart_dir / "templates"
    if not values_path.exists() or not templates_dir.exists():
        return HelmSmokeResult(errors=["Helm chart is missing values.yaml or templates/."])

    values = yaml.safe_load(values_path.read_text(encoding="utf-8"))
    for path in REQUIRED_VALUES:
        _lookup(values, path)

    rendered_source = "\n".join(
        path.read_text(encoding="utf-8") for path in templates_dir.glob("*.yaml")
    )
    errors: list[str] = []
    for snippet in REQUIRED_TEMPLATE_SNIPPETS:
        if snippet not in rendered_source:
            errors.append(f"Helm template smoke missing snippet: {snippet}")
    if "OBJECT_STORE_SECRET_KEY:" in rendered_source:
        errors.append("Helm templates must reference object store secrets, not inline them.")
    for env_name in ["DATABASE_URL", "REDIS_URL", "OBJECT_STORE_ACCESS_KEY"]:
        if rendered_source.count(f"name: {env_name}") < 2:
            errors.append(f"server and worker must both include env: {env_name}")
    if ".Values.objectStore.external.secretRef" not in rendered_source:
        errors.append("objectStore.external.secretRef must be used by workload templates.")

    checked_steps = [
        "values",
        "templates",
        "migration-job",
        "networkpolicy",
        "pdb",
        "servicemonitor",
    ]
    return HelmSmokeResult(errors=errors, checked_steps=checked_steps)


def run_cluster_smoke(
    root: Path,
    *,
    runner: HelmSmokeRunner | None = None,
    cluster_runtime: str = "kind",
) -> HelmSmokeResult:
    active_runner = runner or SubprocessHelmSmokeRunner()
    static_result = validate_helm_chart(root)
    if not static_result.ok:
        return static_result

    commands = _cluster_smoke_commands(root, cluster_runtime=cluster_runtime)
    errors: list[str] = []
    checked_steps = list(static_result.checked_steps)
    try:
        _require_tooling(active_runner, cluster_runtime)
        for step, command, timeout_seconds in commands:
            active_runner.run(command, timeout_seconds)
            checked_steps.append(step)
    except Exception as exc:
        errors.append(str(exc))
    finally:
        try:
            cleanup = _cleanup_commands(cluster_runtime)
            for _step, command, timeout_seconds in cleanup:
                active_runner.run(command, timeout_seconds)
        except Exception as exc:
            errors.append(f"cluster cleanup failed: {exc}")
    return HelmSmokeResult(errors=errors, checked_steps=checked_steps)


def _cluster_smoke_commands(
    root: Path,
    *,
    cluster_runtime: str,
) -> list[tuple[str, list[str], int]]:
    chart_dir = root / "deploy/helm/dimoorun"
    values_path = chart_dir / "values.yaml"
    if cluster_runtime == "k3d":
        cluster_create = ["k3d", "cluster", "create", HELM_RELEASE, "--wait"]
    else:
        cluster_create = ["kind", "create", "cluster", "--name", HELM_RELEASE, "--wait", "120s"]
    return [
        ("cluster-create", cluster_create, 300),
        (
            "namespace-create",
            ["kubectl", "create", "namespace", HELM_NAMESPACE],
            60,
        ),
        (
            "seed-postgres-secret",
            [
                "kubectl",
                "create",
                "secret",
                "generic",
                "dimoorun-postgres-url",
                "--namespace",
                HELM_NAMESPACE,
                "--from-literal=url=postgresql+psycopg://dimoorun:dimoorun@postgres:5432/dimoorun",
            ],
            60,
        ),
        (
            "seed-redis-secret",
            [
                "kubectl",
                "create",
                "secret",
                "generic",
                "dimoorun-redis-url",
                "--namespace",
                HELM_NAMESPACE,
                "--from-literal=url=redis://redis:6379/0",
            ],
            60,
        ),
        (
            "seed-object-store-secret",
            [
                "kubectl",
                "create",
                "secret",
                "generic",
                "dimoorun-object-store",
                "--namespace",
                HELM_NAMESPACE,
                "--from-literal=accessKey=dimoorun",
                "--from-literal=secretKey=dimoorun-dev-secret",
            ],
            60,
        ),
        (
            "helm-template",
            [
                "helm",
                "template",
                HELM_RELEASE,
                str(chart_dir),
                "--namespace",
                HELM_NAMESPACE,
                "-f",
                str(values_path),
                *LIVE_SMOKE_HELM_SET_ARGS,
            ],
            120,
        ),
        (
            "helm-install",
            [
                "helm",
                "upgrade",
                "--install",
                HELM_RELEASE,
                str(chart_dir),
                "--namespace",
                HELM_NAMESPACE,
                "--create-namespace",
                "--wait",
                "--timeout",
                HELM_TIMEOUT,
                "-f",
                str(values_path),
                *LIVE_SMOKE_HELM_SET_ARGS,
            ],
            300,
        ),
        (
            "release-status",
            [
                "helm",
                "status",
                HELM_RELEASE,
                "--namespace",
                HELM_NAMESPACE,
            ],
            60,
        ),
        (
            "resources-present",
            [
                "kubectl",
                "get",
                "deployment,service,configmap,serviceaccount,networkpolicy,poddisruptionbudget",
                "--namespace",
                HELM_NAMESPACE,
            ],
            60,
        ),
    ]


def _cleanup_commands(cluster_runtime: str) -> list[tuple[str, list[str], int]]:
    namespace_delete = [
        "kubectl",
        "delete",
        "namespace",
        HELM_NAMESPACE,
        "--ignore-not-found=true",
        "--wait=true",
    ]
    if cluster_runtime == "k3d":
        cluster_delete = ["k3d", "cluster", "delete", HELM_RELEASE]
    else:
        cluster_delete = ["kind", "delete", "cluster", "--name", HELM_RELEASE]
    return [
        ("namespace-delete", namespace_delete, 300),
        ("cluster-delete", cluster_delete, 300),
    ]


def _require_tooling(runner: HelmSmokeRunner, cluster_runtime: str) -> None:
    required = ["helm", "kubectl", cluster_runtime]
    missing = [name for name in required if not runner.available(name)]
    if missing:
        missing_text = ", ".join(missing)
        raise SystemExit(f"Helm runtime smoke requires installed tooling: {missing_text}")


def _lookup(values: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = values
    for key in path:
        if not isinstance(current, dict) or key not in current:
            raise SystemExit(f"values.yaml missing key: {'.'.join(path)}")
        current = current[key]
    return current


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the DimooRun Helm chart.")
    parser.add_argument(
        "--cluster-runtime",
        choices=["kind", "k3d"],
        help="Run live smoke against an ephemeral cluster runtime.",
    )
    args = parser.parse_args()

    root = Path(".")
    if args.cluster_runtime:
        result = run_cluster_smoke(root, cluster_runtime=args.cluster_runtime)
    else:
        result = validate_helm_chart(root)
    if not result.ok:
        for error in result.errors:
            print(f"Helm chart smoke failed: {error}")
        raise SystemExit(1)
    print("Helm chart smoke passed: " + ", ".join(result.checked_steps))


if __name__ == "__main__":
    main()
