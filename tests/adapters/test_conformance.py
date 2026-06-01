import pytest
from dimoo_run.adapters.base.conformance import ConformanceStatus, run_conformance_suite
from dimoo_run.adapters.langgraph.adapter import LangGraphAdapter
from dimoo_run.core.context import RuntimeContext


class FakeGraph:
    async def ainvoke(self, input_data, config):  # type: ignore[no-untyped-def]
        return {"ok": input_data["ok"]}

    async def astream(self, input_data, config):  # type: ignore[no-untyped-def]
        yield {"ok": input_data["ok"]}


def make_context() -> RuntimeContext:
    return RuntimeContext(
        tenant_id=1,
        project_id=1,
        run_id=1,
        task_id=1,
        agent_id=1,
        agent_version_id="agent_version_1",
        deployment_id=1,
    )


@pytest.mark.asyncio
async def test_conformance_report_records_versions_and_results() -> None:
    report = await run_conformance_suite(
        adapter=LangGraphAdapter(),
        agent=FakeGraph(),
        context=make_context(),
        input_data={"ok": True},
    )

    assert report.status == ConformanceStatus.certified_with_limitations
    assert report.framework == "langgraph"
    assert report.adapter_api_version == "1.0"
    assert report.framework_version
    assert report.tests["invoke"] == "passed"
    assert report.tests["stream"] == "passed"
    assert report.tests["resume"] == "unsupported"
    assert report.tests["cancel"] == "not_exercised"
    assert report.tests["checkpoint"] == "not_exercised"
    assert report.tests["idempotency"] == "not_exercised"
    assert report.failed == []
