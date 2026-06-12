import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.helm_smoke import HELM_NAMESPACE, HELM_RELEASE, run_cluster_smoke

CHART_DIR = Path("deploy/helm/dimoorun")


def test_helm_chart_declares_enterprise_values_and_workloads() -> None:
    values = yaml.safe_load((CHART_DIR / "values.yaml").read_text(encoding="utf-8"))
    template_names = {path.name for path in (CHART_DIR / "templates").glob("*.yaml")}

    assert values["server"]["replicas"] >= 2
    assert values["worker"]["replicas"] >= 2
    assert values["postgres"]["external"]["enabled"] is True
    assert values["redis"]["external"]["enabled"] is True
    assert values["objectStore"]["external"]["enabled"] is True
    assert values["secretProvider"]["mode"] == "kubernetes"
    assert values["sandbox"]["mode"] == "container"
    assert {
        "server.yaml",
        "worker.yaml",
        "console.yaml",
        "configmap.yaml",
        "serviceaccount.yaml",
        "ingress.yaml",
        "hpa.yaml",
        "migration-job.yaml",
        "networkpolicy.yaml",
        "pdb.yaml",
        "servicemonitor.yaml",
    } <= template_names
    assert values["resources"]["defaults"]["requests"]["cpu"] == "250m"
    assert values["migrationJob"]["enabled"] is True
    assert values["networkPolicy"]["enabled"] is True
    assert values["podDisruptionBudget"]["enabled"] is True
    assert values["serviceMonitor"]["enabled"] is True


def test_k8s_templates_include_required_objects_without_embedding_plain_secrets() -> None:
    rendered_source = "\n".join(
        path.read_text(encoding="utf-8") for path in (CHART_DIR / "templates").glob("*.yaml")
    )

    for expected in [
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
    ]:
        assert expected in rendered_source
    assert "OBJECT_STORE_SECRET_KEY:" not in rendered_source
    for env_name in ["DATABASE_URL", "REDIS_URL", "OBJECT_STORE_ACCESS_KEY"]:
        assert rendered_source.count(f"name: {env_name}") >= 2
    assert ".Values.objectStore.external.secretRef" in rendered_source


class FakeHelmRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(self, command: list[str], timeout_seconds: int) -> None:
        _ = timeout_seconds
        self.commands.append(command)

    def available(self, executable: str) -> bool:
        return executable in {"helm", "kubectl", "kind"}


def test_live_cluster_smoke_builds_expected_kind_command_plan() -> None:
    runner = FakeHelmRunner()

    result = run_cluster_smoke(Path("."), runner=runner, cluster_runtime="kind")

    assert result.errors == []
    assert runner.commands == [
        ["kind", "create", "cluster", "--name", HELM_RELEASE, "--wait", "120s"],
        [
            "helm",
            "template",
            HELM_RELEASE,
            str(CHART_DIR),
            "--namespace",
            HELM_NAMESPACE,
            "-f",
            str(CHART_DIR / "values.yaml"),
            "--set",
            "serviceMonitor.enabled=false",
        ],
        [
            "helm",
            "upgrade",
            "--install",
            HELM_RELEASE,
            str(CHART_DIR),
            "--namespace",
            HELM_NAMESPACE,
            "--create-namespace",
            "--wait",
            "--timeout",
            "10m",
            "-f",
            str(CHART_DIR / "values.yaml"),
            "--set",
            "serviceMonitor.enabled=false",
        ],
        [
            "kubectl",
            "wait",
            "--namespace",
            HELM_NAMESPACE,
            "--for=condition=complete",
            f"job/{HELM_RELEASE}-migration",
            "--timeout=300s",
        ],
        [
            "kubectl",
            "wait",
            "--namespace",
            HELM_NAMESPACE,
            "--for=condition=available",
            "deployment",
            "--all",
            "--timeout=300s",
        ],
        [
            "kubectl",
            "get",
            "job",
            "--namespace",
            HELM_NAMESPACE,
            f"{HELM_RELEASE}-migration",
            "-o",
            "yaml",
        ],
        [
            "kubectl",
            "delete",
            "namespace",
            HELM_NAMESPACE,
            "--ignore-not-found=true",
            "--wait=true",
        ],
        ["kind", "delete", "cluster", "--name", HELM_RELEASE],
    ]
