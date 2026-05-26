from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from dimoo_run.observability.policies import RedactionPolicy


class DatasetScopeMismatchError(PermissionError):
    error_code = "dataset_scope_mismatch"


@dataclass(frozen=True)
class Dataset:
    id: str
    tenant_id: str
    project_id: str
    name: str
    source: str
    schema: dict[str, Any]
    created_by: str
    description: str | None = None
    visibility_level: str = "internal"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class DatasetItem:
    id: str
    tenant_id: str
    project_id: str
    dataset_id: str
    source_run_id: str | None
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    expected: dict[str, Any] | None
    created_by: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class DatasetService:
    def __init__(self, *, redacted_fields: set[str] | None = None) -> None:
        self.redacted_fields = redacted_fields or set()
        self.redaction_policy = RedactionPolicy(fields=self.redacted_fields)
        self.datasets: dict[str, Dataset] = {}
        self.items: dict[str, DatasetItem] = {}

    def create_dataset(
        self,
        *,
        tenant_id: str,
        project_id: str,
        name: str,
        source: str,
        schema: dict[str, Any],
        created_by: str,
        description: str | None = None,
    ) -> Dataset:
        dataset = Dataset(
            id=str(uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            source=source,
            schema=schema,
            created_by=created_by,
            description=description,
        )
        self.datasets[dataset.id] = dataset
        return dataset

    def add_item_from_run(
        self,
        *,
        dataset_id: str,
        tenant_id: str,
        project_id: str,
        run_id: str,
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
            id=str(uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            dataset_id=dataset_id,
            source_run_id=run_id,
            input_data=self.redaction_policy.apply(input_data),
            output_data=self.redaction_policy.apply(output_data),
            expected=self.redaction_policy.apply(expected) if expected is not None else None,
            created_by=created_by,
        )
        self.items[item.id] = item
        return item
