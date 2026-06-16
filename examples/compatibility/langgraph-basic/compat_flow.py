from __future__ import annotations

import argparse
import json
from typing import Any

import httpx


def main() -> None:
    args = parse_args()
    headers = {
        "Authorization": f"Bearer {args.api_key}",
        "X-Tenant-Id": str(args.tenant_id),
        "X-Project-Id": str(args.project_id),
        "X-Request-Id": "req_compat_example",
    }
    with httpx.Client(base_url=args.base_url, headers=headers, timeout=30) as client:
        migration = post_json(
            client,
            "/v1/console/compatibility/migration-report",
            {
                "framework": "langgraph",
                "adapter": "langgraph",
                "capabilities": ["assistants", "threads", "runs", "stream", "hosted_deployments"],
                "streaming_modes": ["events"],
                "uses_checkpointing": True,
            },
        )
        assistant = post_json(
            client,
            "/compat/langgraph/assistants",
            {"name": "compatibility-basic"},
        )
        thread = post_json(
            client,
            "/compat/langgraph/threads",
            {"metadata": {"label": "compat-basic"}},
        )
        run = post_json(
            client,
            f"/compat/langgraph/threads/{thread['thread_id']}/runs",
            {"assistant_id": assistant["assistant_id"], "input": {"message": "hello compatibility"}},
        )
        stream_text = post_stream(
            client,
            f"/compat/langgraph/threads/{thread['thread_id']}/runs/stream",
            {"assistant_id": assistant["assistant_id"], "input": {"message": "stream compatibility"}},
        )
        replay = client.get(
            f"/compat/langgraph/threads/{thread['thread_id']}/runs/{run['run_id']}/events",
            params={"last_event_id": f"{run['run_id']}:1"},
        )
        replay.raise_for_status()
        cancel = post_json(
            client,
            f"/compat/langgraph/threads/{thread['thread_id']}/runs/{run['run_id']}/cancel",
            {},
        )
    print(
        json.dumps(
            {
                "migration_status": migration["report"]["overall_status"],
                "assistant_id": assistant["assistant_id"],
                "thread_id": thread["thread_id"],
                "run_id": run["run_id"],
                "task_id": run["metadata"]["dimoorun_mapping"]["task_id"],
                "stream_contains_run_created": "event: run.created" in stream_text,
                "replay_event_count": len(replay.json().get("events", [])),
                "cancel_status": cancel["status"],
                "native_evidence": {
                    "run": f"/runs/{run['run_id']}",
                    "task_id": run["metadata"]["dimoorun_mapping"]["task_id"],
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


def post_json(client: httpx.Client, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(path, json=payload)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} did not return a JSON object")
    return data


def post_stream(client: httpx.Client, path: str, payload: dict[str, Any]) -> str:
    response = client.post(path, json=payload)
    response.raise_for_status()
    return response.text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--project-id", type=int, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    main()
