from pathlib import Path

import yaml

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
    } <= template_names


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
        "secretKeyRef",
    ]:
        assert expected in rendered_source
    assert "OBJECT_STORE_SECRET_KEY:" not in rendered_source
    for env_name in ["DATABASE_URL", "REDIS_URL", "OBJECT_STORE_ACCESS_KEY"]:
        assert rendered_source.count(f"name: {env_name}") >= 2
    assert ".Values.objectStore.external.secretRef" in rendered_source
