from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REQUIRED_VALUES = [
    ("server", "replicas"),
    ("worker", "replicas"),
    ("console", "ingress"),
    ("postgres", "external"),
    ("redis", "external"),
    ("objectStore", "external"),
    ("secretProvider", "mode"),
    ("sandbox", "mode"),
    ("resources",),
    ("autoscaling",),
]

REQUIRED_TEMPLATE_SNIPPETS = [
    "kind: Deployment",
    "kind: Service",
    "kind: Ingress",
    "kind: ConfigMap",
    "kind: ServiceAccount",
    "kind: HorizontalPodAutoscaler",
    "secretKeyRef",
]


def main() -> None:
    chart_dir = Path("deploy/helm/dimoorun")
    values_path = chart_dir / "values.yaml"
    templates_dir = chart_dir / "templates"
    if not values_path.exists() or not templates_dir.exists():
        raise SystemExit("Helm chart is missing values.yaml or templates/.")
    values = yaml.safe_load(values_path.read_text(encoding="utf-8"))
    for path in REQUIRED_VALUES:
        _lookup(values, path)
    rendered_source = "\n".join(
        path.read_text(encoding="utf-8") for path in templates_dir.glob("*.yaml")
    )
    for snippet in REQUIRED_TEMPLATE_SNIPPETS:
        if snippet not in rendered_source:
            raise SystemExit(f"Helm template smoke missing snippet: {snippet}")
    if "OBJECT_STORE_SECRET_KEY:" in rendered_source:
        raise SystemExit("Helm templates must reference object store secrets, not inline them.")
    for env_name in ["DATABASE_URL", "REDIS_URL", "OBJECT_STORE_ACCESS_KEY"]:
        if rendered_source.count(f"name: {env_name}") < 2:
            raise SystemExit(f"server and worker must both include env: {env_name}")
    if ".Values.objectStore.external.secretRef" not in rendered_source:
        raise SystemExit("objectStore.external.secretRef must be used by workload templates.")
    print("Helm chart smoke passed.")


def _lookup(values: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = values
    for key in path:
        if not isinstance(current, dict) or key not in current:
            raise SystemExit(f"values.yaml missing key: {'.'.join(path)}")
        current = current[key]
    return current


if __name__ == "__main__":
    main()
