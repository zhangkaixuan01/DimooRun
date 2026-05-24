import importlib
import sys
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast


@contextmanager
def package_import_path(package_uri: str | Path):  # type: ignore[no-untyped-def]
    package_path = Path(package_uri).resolve()
    sys.path.insert(0, str(package_path))
    try:
        yield
    finally:
        try:
            sys.path.remove(str(package_path))
        except ValueError:
            pass


def _module_names_loaded_from(package_path: Path) -> list[str]:
    loaded_names: list[str] = []
    for name, module in sys.modules.items():
        module_file = getattr(module, "__file__", None)
        if module_file is None:
            continue
        try:
            resolved_file = Path(module_file).resolve()
        except OSError:
            continue
        if resolved_file.is_relative_to(package_path):
            loaded_names.append(name)
    return loaded_names


def _package_candidate_module_names(package_path: Path) -> set[str]:
    names: set[str] = set()
    for child in package_path.iterdir():
        if child.name.startswith("."):
            continue
        if child.is_file() and child.suffix == ".py" and child.stem != "__init__":
            names.add(child.stem)
        elif child.is_dir() and (child / "__init__.py").exists():
            names.add(child.name)
    return names


def _snapshot_modules(module_names: set[str]) -> dict[str, Any]:
    return {
        name: module
        for name, module in sys.modules.items()
        if any(
            name == module_name or name.startswith(f"{module_name}.")
            for module_name in module_names
        )
    }


def _remove_modules(module_names: set[str]) -> None:
    for name in [
        key
        for key in sys.modules
        if any(
            key == module_name or key.startswith(f"{module_name}.")
            for module_name in module_names
        )
    ]:
        sys.modules.pop(name, None)


def _load_entrypoint_in_active_path(package_path: Path, entrypoint: str) -> Callable[..., Any]:
    module_name, function_name = entrypoint.split(":", maxsplit=1)
    module_names = {module_name}
    original_modules = _snapshot_modules(module_names)
    _remove_modules(module_names)
    try:
        module = importlib.import_module(module_name)
    finally:
        _remove_modules(module_names)
        sys.modules.update(original_modules)
    loaded = getattr(module, function_name)
    if not callable(loaded):
        raise TypeError(f"Entrypoint {entrypoint} is not callable.")
    return cast(Callable[..., Any], loaded)


def load_entrypoint(package_uri: str | Path, entrypoint: str) -> Callable[..., Any]:
    package_path = Path(package_uri).resolve()
    with package_import_path(package_path):
        return _load_entrypoint_in_active_path(package_path, entrypoint)


def load_entrypoint_result(package_uri: str | Path, entrypoint: str, config: dict[str, Any]) -> Any:
    package_path = Path(package_uri).resolve()
    package_module_names = _package_candidate_module_names(package_path)
    original_modules = _snapshot_modules(package_module_names)
    before_names = set(sys.modules)
    with package_import_path(package_path):
        try:
            _remove_modules(package_module_names)
            loaded = _load_entrypoint_in_active_path(package_path, entrypoint)
            return loaded(config)
        finally:
            package_loaded_names = set(_module_names_loaded_from(package_path))
            for name in (set(sys.modules) - before_names) | package_loaded_names:
                sys.modules.pop(name, None)
            sys.modules.update(original_modules)
