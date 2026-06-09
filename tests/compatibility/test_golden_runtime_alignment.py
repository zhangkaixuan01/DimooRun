from dimoo_run.compatibility.golden_runner import GoldenCompatibilityRunner


def test_golden_runner_records_native_resources_and_divergence() -> None:
    runner = GoldenCompatibilityRunner()

    record = runner.record(
        operation="run.stream_probe",
        expected_semantics={"operation": "run.stream_probe"},
        compat_response={"status": "running"},
        native_resources={"run_id": 11, "task_id": 22},
        unsupported_capabilities=["hosted_deployments"],
    )

    assert record["operation"] == "run.stream_probe"
    assert record["native_resources"] == {"run_id": 11, "task_id": 22}
    assert record["unsupported_capabilities"] == ["hosted_deployments"]
    assert record["divergence_reason"] == "compatibility_not_supported"


def test_golden_runner_preserves_structured_expected_semantics() -> None:
    runner = GoldenCompatibilityRunner()

    record = runner.record(
        operation="run.replay",
        expected_semantics={
            "operation": "run.replay",
            "supports_last_event_id_replay": True,
            "replayed_event_types": ["task.queued", "run.started"],
        },
        compat_response={"status": "running"},
        native_resources={"run_id": 12, "task_id": 23},
    )

    assert record["expected_semantics"]["supports_last_event_id_replay"] is True
    assert record["expected_semantics"]["replayed_event_types"] == [
        "task.queued",
        "run.started",
    ]
    assert record["divergence_reason"] is None
