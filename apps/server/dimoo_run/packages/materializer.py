from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from dimoo_run.core.config import Settings


class PackageMaterializationError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(error_code)


@dataclass(frozen=True)
class MaterializedPackage:
    source_uri: str
    load_path: str
    source_path: str


@dataclass(frozen=True)
class OciPackageReference:
    registry: str
    repository: str
    reference: str


class OciPackageMaterializer:
    def __init__(
        self,
        *,
        cache_root: str | Path,
        oci_roots: Sequence[str | Path],
    ) -> None:
        self.cache_root = Path(cache_root).resolve()
        self.oci_roots = [Path(root).resolve() for root in oci_roots]

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> OciPackageMaterializer:
        current = settings or Settings.from_env()
        return cls(
            cache_root=current.packages.cache_root,
            oci_roots=current.packages.oci_roots,
        )

    def materialize(self, package_uri: str) -> MaterializedPackage:
        reference = parse_oci_package_uri(package_uri)
        source_path = self._find_source(reference)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        cache_dir = self.cache_root / hashlib.sha256(package_uri.encode("utf-8")).hexdigest()
        marker_path = cache_dir / ".materialized.json"
        if marker_path.exists():
            payload = json.loads(marker_path.read_text(encoding="utf-8"))
            load_path = cache_dir / payload["relative_load_path"]
            if load_path.exists():
                return MaterializedPackage(
                    source_uri=package_uri,
                    load_path=str(load_path),
                    source_path=str(source_path),
                )
        staging_dir = self.cache_root / f".staging-{uuid4().hex}"
        staging_dir.mkdir(parents=True, exist_ok=False)
        try:
            load_path = self._materialize_source(source_path, staging_dir / "package")
            relative_load_path = str(load_path.relative_to(staging_dir))
            marker_payload = {
                "source_uri": package_uri,
                "relative_load_path": relative_load_path,
            }
            (staging_dir / ".materialized.json").write_text(
                json.dumps(marker_payload, sort_keys=True),
                encoding="utf-8",
            )
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
            staging_dir.rename(cache_dir)
        except Exception:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise
        return MaterializedPackage(
            source_uri=package_uri,
            load_path=str(cache_dir / relative_load_path),
            source_path=str(source_path),
        )

    def _find_source(self, reference: OciPackageReference) -> Path:
        candidates = list(_candidate_source_paths(reference, self.oci_roots))
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise PackageMaterializationError("oci_package_not_found")

    def _materialize_source(self, source_path: Path, target_dir: Path) -> Path:
        if source_path.is_dir():
            shutil.copytree(source_path, target_dir)
            return _normalized_package_root(target_dir)
        target_dir.mkdir(parents=True, exist_ok=False)
        if source_path.suffix == ".zip":
            with zipfile.ZipFile(source_path) as archive:
                _safe_extract_zip(archive, target_dir)
        else:
            with tarfile.open(source_path) as archive:
                _safe_extract_tar(archive, target_dir)
        return _normalized_package_root(target_dir)


def parse_oci_package_uri(package_uri: str) -> OciPackageReference:
    if not package_uri.startswith("oci://"):
        raise PackageMaterializationError("oci_package_uri_invalid")
    remainder = package_uri.removeprefix("oci://")
    if "/" not in remainder:
        raise PackageMaterializationError("oci_package_uri_invalid")
    if "@sha256:" in remainder:
        name, digest = remainder.split("@", maxsplit=1)
        reference = digest.replace(":", "-")
    else:
        name, separator, reference = remainder.rpartition(":")
        if separator != ":" or not name or "/" not in name or not reference:
            raise PackageMaterializationError("oci_package_uri_invalid")
    registry, repository = name.split("/", maxsplit=1)
    if not registry or not repository:
        raise PackageMaterializationError("oci_package_uri_invalid")
    return OciPackageReference(
        registry=registry,
        repository=repository,
        reference=reference,
    )


def _candidate_source_paths(
    reference: OciPackageReference,
    roots: list[Path],
) -> list[Path]:
    repository_path = Path(*reference.repository.split("/"))
    ref_name = reference.reference
    candidates: list[Path] = []
    for root in roots:
        base = root / reference.registry / repository_path
        candidates.extend(
            [
                base / ref_name,
                base / ref_name / "package",
                base / f"{ref_name}.tar.gz",
                base / ref_name / "package.tar.gz",
                base / f"{ref_name}.tgz",
                base / ref_name / "package.tgz",
                base / f"{ref_name}.zip",
                base / ref_name / "package.zip",
            ]
        )
    return candidates


def _normalized_package_root(path: Path) -> Path:
    visible_children = [child for child in path.iterdir() if not child.name.startswith(".")]
    if len(visible_children) == 1 and visible_children[0].is_dir():
        child = visible_children[0]
        markers = {child / "manifest.yaml", child / "pyproject.toml"}
        if any(marker.exists() for marker in markers):
            return child
    return path


def _safe_extract_tar(archive: tarfile.TarFile, target_dir: Path) -> None:
    for member in archive.getmembers():
        member_path = target_dir / member.name
        resolved_member = member_path.resolve()
        if not resolved_member.is_relative_to(target_dir.resolve()):
            raise PackageMaterializationError("oci_package_archive_unsafe_path")
    archive.extractall(target_dir)


def _safe_extract_zip(archive: zipfile.ZipFile, target_dir: Path) -> None:
    for name in archive.namelist():
        resolved_member = (target_dir / name).resolve()
        if not resolved_member.is_relative_to(target_dir.resolve()):
            raise PackageMaterializationError("oci_package_archive_unsafe_path")
    archive.extractall(target_dir)
