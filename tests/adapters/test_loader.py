import sys
from types import ModuleType

from dimoo_run.packages.loader import load_entrypoint, load_entrypoint_result


def test_load_entrypoint_from_package_directory(tmp_path) -> None:  # type: ignore[no-untyped-def]
    package_dir = tmp_path / "agent_package"
    package_dir.mkdir()
    (package_dir / "agent.py").write_text(
        "def build_graph(config):\n    return {'config': config}\n",
        encoding="utf-8",
    )

    entrypoint = load_entrypoint(package_dir, "agent:build_graph")

    assert entrypoint({"mode": "test"}) == {"config": {"mode": "test"}}


def test_load_entrypoint_does_not_reuse_same_named_module_cache(tmp_path) -> None:  # type: ignore[no-untyped-def]
    first_package = tmp_path / "first_package"
    second_package = tmp_path / "second_package"
    first_package.mkdir()
    second_package.mkdir()
    (first_package / "agent.py").write_text(
        "def build_graph(config):\n    return 'first'\n",
        encoding="utf-8",
    )
    (second_package / "agent.py").write_text(
        "def build_graph(config):\n    return 'second'\n",
        encoding="utf-8",
    )

    first_entrypoint = load_entrypoint(first_package, "agent:build_graph")
    second_entrypoint = load_entrypoint(second_package, "agent:build_graph")

    assert first_entrypoint({}) == "first"
    assert second_entrypoint({}) == "second"


def test_load_entrypoint_restores_existing_module_cache(tmp_path) -> None:  # type: ignore[no-untyped-def]
    package_dir = tmp_path / "agent_package"
    package_dir.mkdir()
    (package_dir / "agent.py").write_text(
        "def build_graph(config):\n    return 'package-agent'\n",
        encoding="utf-8",
    )
    existing_module = ModuleType("agent")
    existing_module.marker = "existing"  # type: ignore[attr-defined]
    sys.modules["agent"] = existing_module

    try:
        entrypoint = load_entrypoint(package_dir, "agent:build_graph")

        assert entrypoint({}) == "package-agent"
        assert sys.modules["agent"] is existing_module
    finally:
        sys.modules.pop("agent", None)


def test_load_entrypoint_result_keeps_package_path_during_entrypoint_call(tmp_path) -> None:  # type: ignore[no-untyped-def]
    package_dir = tmp_path / "agent_package"
    package_dir.mkdir()
    (package_dir / "agent.py").write_text(
        "def build_graph(config):\n"
        "    import helper\n"
        "    return helper.build(config)\n",
        encoding="utf-8",
    )
    (package_dir / "helper.py").write_text(
        "def build(config):\n    return {'helper': config['name']}\n",
        encoding="utf-8",
    )

    result = load_entrypoint_result(package_dir, "agent:build_graph", {"name": "package"})

    assert result == {"helper": "package"}


def test_load_entrypoint_result_does_not_reuse_top_level_helper_modules(tmp_path) -> None:  # type: ignore[no-untyped-def]
    first_package = tmp_path / "first_package"
    second_package = tmp_path / "second_package"
    first_package.mkdir()
    second_package.mkdir()
    (first_package / "agent.py").write_text(
        "def build_graph(config):\n"
        "    import helper\n"
        "    return helper.NAME\n",
        encoding="utf-8",
    )
    (first_package / "helper.py").write_text("NAME = 'first'\n", encoding="utf-8")
    (second_package / "agent.py").write_text(
        "def build_graph(config):\n"
        "    import helper\n"
        "    return helper.NAME\n",
        encoding="utf-8",
    )
    (second_package / "helper.py").write_text("NAME = 'second'\n", encoding="utf-8")

    first_result = load_entrypoint_result(first_package, "agent:build_graph", {})
    second_result = load_entrypoint_result(second_package, "agent:build_graph", {})

    assert first_result == "first"
    assert second_result == "second"
    assert "helper" not in sys.modules


def test_load_entrypoint_result_prefers_package_helper_and_restores_host_module(tmp_path) -> None:  # type: ignore[no-untyped-def]
    package_dir = tmp_path / "agent_package"
    package_dir.mkdir()
    (package_dir / "agent.py").write_text(
        "def build_graph(config):\n"
        "    import helper\n"
        "    return helper.NAME\n",
        encoding="utf-8",
    )
    (package_dir / "helper.py").write_text("NAME = 'package'\n", encoding="utf-8")
    existing_helper = ModuleType("helper")
    existing_helper.NAME = "host"  # type: ignore[attr-defined]
    sys.modules["helper"] = existing_helper

    try:
        result = load_entrypoint_result(package_dir, "agent:build_graph", {})

        assert result == "package"
        assert sys.modules["helper"] is existing_helper
    finally:
        sys.modules.pop("helper", None)
