# LiteLLM Integration Proof

DimooRun does not replace LiteLLM. LiteLLM remains the model gateway; DimooRun records the gateway routing evidence on the Run so operators can connect model cost, route, and failure triage.

## Record Gateway Evidence

After a run is created, write LiteLLM routing evidence through the native API:

```bash
curl -X POST "$DIMOORUN_API_BASE_URL/v1/runs/$RUN_ID/integration-evidence" \
  -H "Authorization: Bearer $DIMOORUN_API_KEY" \
  -H "X-Tenant-Id: 1" \
  -H "X-Project-Id: 1" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "litellm-local-proof",
    "model_gateway": {
      "provider": "litellm",
      "gateway_name": "local-litellm",
      "gateway_request_id": "gw_req_1001",
      "model": "gpt-4.1-mini",
      "route": "support-policy",
      "prompt_tokens": 118,
      "completion_tokens": 42,
      "total_tokens": 160,
      "cost": 0.0042,
      "currency": "USD"
    }
  }'
```

## Verify

Open `Console -> Runs -> Run Detail -> Integration evidence`. The model routing card should show `litellm`, the routed model, request id or route, token count, and cost.

Automated proof:

```bash
uv run pytest tests/api/test_native_api.py::test_run_integration_evidence_is_written_through_real_api -q
```
