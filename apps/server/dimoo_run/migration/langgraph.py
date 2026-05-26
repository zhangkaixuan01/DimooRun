import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class MigrationReport:
    manifest_path: Path
    project_config_path: Path
    report_path: Path
    source_type: str
    detected_entrypoint: str
    detected_capabilities: dict[str, str]
    warnings: list[str]
    compatibility_warnings: list[str]


def migrate_langgraph_project(
    source_path: str | Path,
    output_path: str | Path,
    *,
    project_name: str,
    source_type: str = "langgraph",
    source_warnings: list[str] | None = None,
) -> MigrationReport:
    source = Path(source_path)
    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=True)

    detected = _detect_project(source)
    entrypoint = detected["entrypoint"]
    warnings = ["checkpoint migration is best-effort", *(source_warnings or [])]
    compatibility_warnings: list[str] = []
    if any(source.glob("checkpoint*")) or detected.get("checkpoint_backend") is not None:
        compatibility_warnings.append("checkpoint_incompatible")
    if len(detected["graphs"]) > 1:
        compatibility_warnings.append("multiple_graphs_detected")

    manifest_path = output / "manifest.yaml"
    project_config_path = output / "dimoorun.yaml"
    report_path = output / "migration_report.md"

    manifest_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "name": project_name,
                "version": "0.1.0",
                "runtime": {
                    "framework": "langgraph",
                    "adapter": "langgraph",
                    "entrypoint": entrypoint,
                    "python": ">=3.11",
                },
                "capabilities": {"invoke": True, "stream": True, "checkpoint": True},
                "dependencies": detected["dependencies"],
                "required_secrets": ["NEWAPI_API_KEY"],
                "security": {"network_policy": "restricted", "allow_file_system_write": False},
                "metadata": {
                    "migration_source": str(source),
                    "langgraph_config": detected.get("langgraph_config"),
                    "checkpoint_backend": detected.get("checkpoint_backend"),
                    "store_backend": detected.get("store_backend"),
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    project_config_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "project": {"name": project_name, "tenant": "default"},
                "agents": [
                    {
                        "name": project_name,
                        "path": ".",
                        "manifest": "./manifest.yaml",
                    }
                ],
                "adapters": {
                    "langgraph": {"enabled": True},
                    "langchain-agent": {"enabled": False},
                    "deepagents": {"enabled": False},
                },
                "deployments": {
                    "dev": {
                        "agent": project_name,
                        "version": "0.1.0",
                        "execution_profile": "local-dev",
                    }
                },
                "execution_profiles": {"local-dev": {"mode": "in_process", "storage": "sqlite"}},
                "model_gateways": {"default": {"provider": "newapi", "secret": "NEWAPI_API_KEY"}},
                "policies": {"tool_approval": {"destructive": "required"}},
                "observability": {"tracing": "opentelemetry", "langfuse": {"enabled": False}},
                "storage": {"metadata": "sqlite", "queue": "in_process", "object_store": "local"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    report_path.write_text(
        "\n".join(
            [
                f"# Migration Report: {project_name}",
                "",
                f"- Source: `{source}`",
                f"- source type: {source_type}",
                f"- Entrypoint: `{entrypoint}`",
                f"- config: {detected.get('langgraph_config') or 'not detected'}",
                f"- env file: {detected.get('env_file') or 'not detected'}",
                "- Graphs:",
                *[
                    f"  - {name} -> {graph_entrypoint}"
                    for name, graph_entrypoint in detected["graphs"].items()
                ],
                f"- Dependencies: {', '.join(detected['dependencies']) or 'not detected'}",
                f"- checkpoint backend: {detected.get('checkpoint_backend') or 'not detected'}",
                f"- store backend: {detected.get('store_backend') or 'not detected'}",
                f"- Warnings: {', '.join(warnings) or 'none'}",
                f"- Compatibility warnings: {', '.join(compatibility_warnings) or 'none'}",
            ]
        ),
        encoding="utf-8",
    )
    return MigrationReport(
        manifest_path=manifest_path,
        project_config_path=project_config_path,
        report_path=report_path,
        source_type=source_type,
        detected_entrypoint=entrypoint,
        detected_capabilities={
            "langgraph_config": str(detected.get("langgraph_config") or ""),
            "checkpoint_backend": str(detected.get("checkpoint_backend") or ""),
            "store_backend": str(detected.get("store_backend") or ""),
            "env_file": str(detected.get("env_file") or ""),
        },
        warnings=warnings,
        compatibility_warnings=compatibility_warnings,
    )


def _detect_project(source: Path) -> dict[str, Any]:
    dependencies = _detect_dependencies(source)
    langgraph_config = _read_langgraph_config(source)
    return {
        "graphs": _detect_graphs(langgraph_config),
        "entrypoint": _detect_entrypoint(source, langgraph_config),
        "dependencies": dependencies,
        "langgraph_config": "langgraph.json" if langgraph_config else None,
        "env_file": langgraph_config.get("env") if langgraph_config else None,
        "checkpoint_backend": _detect_backend(dependencies, prefix="langgraph-checkpoint"),
        "store_backend": _detect_backend(dependencies, prefix="langgraph-store"),
    }


def _read_langgraph_config(source: Path) -> dict[str, Any] | None:
    config_path = source / "langgraph.json"
    if not config_path.exists():
        return None
    return dict(json.loads(config_path.read_text(encoding="utf-8")))


def _detect_dependencies(source: Path) -> list[str]:
    pyproject_path = source / "pyproject.toml"
    if not pyproject_path.exists():
        return []
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = payload.get("project", {})
    dependencies = project.get("dependencies", [])
    if not isinstance(dependencies, list):
        return []
    return [str(dependency) for dependency in dependencies]


def _detect_backend(dependencies: list[str], *, prefix: str) -> str | None:
    for dependency in dependencies:
        package = dependency.split("[", maxsplit=1)[0].split("=", maxsplit=1)[0].strip()
        if package.startswith(prefix):
            return package
    return None


def _detect_entrypoint(source: Path, langgraph_config: dict[str, Any] | None = None) -> str:
    graphs = _detect_graphs(langgraph_config)
    if graphs:
        return next(iter(graphs.values()))
    if (source / "agent.py").exists():
        return "agent:create_agent"
    candidates = sorted(source.glob("*.py"))
    if candidates:
        return f"{candidates[0].stem}:create_agent"
    return "agent:create_agent"


def _detect_graphs(langgraph_config: dict[str, Any] | None = None) -> dict[str, str]:
    if langgraph_config is None:
        return {}
    graphs = langgraph_config.get("graphs", {})
    if not isinstance(graphs, dict):
        return {}
    return {
        str(name): _normalize_entrypoint(str(raw_entrypoint))
        for name, raw_entrypoint in graphs.items()
    }


def _normalize_entrypoint(raw_entrypoint: str) -> str:
    value = raw_entrypoint.removeprefix("./")
    if ":" not in value:
        return value
    module_path, function_name = value.split(":", maxsplit=1)
    module_name = Path(module_path).with_suffix("").as_posix().replace("/", ".")
    return f"{module_name}:{function_name}"
