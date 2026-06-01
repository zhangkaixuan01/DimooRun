from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from dimoo_run.observability.policies import RedactionPolicy


class DatasetScopeMismatchError(PermissionError):
    error_code = "dataset_scope_mismatch"


@dataclass(frozen=True)
class Dataset:
    id: int
    tenant_id: int
    project_id: int
    name: str
    source: str
    schema: dict[str, Any]
    created_by: str
    description: str | None = None
    visibility_level: str = "internal"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class DatasetItem:
    id: int
    tenant_id: int
    project_id: int
    dataset_id: int
    source_run_id: int | None
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    expected: dict[str, Any] | None
    created_by: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class DatasetService:
    def __init__(self, *, redacted_fields: set[str] | None = None) -> None:
        self.redacted_fields = redacted_fields or set()
        self.redaction_policy = RedactionPolicy(fields=self.redacted_fields)
        self.datasets: dict[int, Dataset] = {}
        self.items: dict[int, DatasetItem] = {}
        self._next_dataset_id = 1
        self._next_item_id = 1

    def create_dataset(
        self,
        *,
        tenant_id: int,
        project_id: int,
        name: str,
        source: str,
        schema: dict[str, Any],
        created_by: str,
        description: str | None = None,
    ) -> Dataset:
        dataset = Dataset(
            id=self._next_dataset_id,
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            source=source,
            schema=schema,
            created_by=created_by,
            description=description,
        )
        self._next_dataset_id += 1
        self.datasets[dataset.id] = dataset
        return dataset

    def add_item_from_run(
        self,
        *,
        dataset_id: int,
        tenant_id: int,
        project_id: int,
        run_id: int,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        expected: dict[str, Any] | None,
        created_by: str,
    ) -> DatasetItem:
        dataset = self.datasets.get(dataset_id)
        if dataset is None:
            raise DatasetScopeMismatchError("dataset_not_found")
        if dataset.tenant_id != tenant_id or dataset.project_id != project_id:
            raise DatasetScopeMismatchError("dataset_scope_mismatch")
        item = DatasetItem(
            id=self._next_item_id,
            tenant_id=tenant_id,
            project_id=project_id,
            dataset_id=dataset_id,
            source_run_id=run_id,
            input_data=self.redaction_policy.apply(input_data),
            output_data=self.redaction_policy.apply(output_data),
            expected=self.redaction_policy.apply(expected) if expected is not None else None,
            created_by=created_by,
        )
        self._next_item_id += 1
        self.items[item.id] = item
        return item
