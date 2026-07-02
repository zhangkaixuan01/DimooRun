# OpenTelemetry Integration Proof

DimooRun does not replace OpenTelemetry. OTel remains the telemetry transport; DimooRun records exporter delivery status and trace correlation on the Run evidence chain.

## Record Exporter Evidence

After a run is created, write exporter evidence through the native API:

```bash
curl -X POST "$DIMOORUN_API_BASE_URL/v1/runs/$RUN_ID/integration-evidence" \
  -H "Authorization: Bearer $DIMOORUN_API_KEY" \
  -H "X-Tenant-Id: 1" \
  -H "X-Project-Id: 1" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "otel-local-proof",
    "exporters": [
      {
        "provider": "opentelemetry",
        "exporter_type": "otlp",
        "target_ref": "http://otel:4318",
        "status": "delivered",
        "request_id": "otel_req_1001"
      }
    ],
    "failures": [
      {
        "provider": "opentelemetry",
        "status": "recovered",
        "error_code": "otlp_retry",
        "message": "First export attempt retried, second delivered",
        "retryable": true
      }
    ]
  }'
```

## Verify

Open `Console -> Runs -> Run Detail -> Integration evidence`. The exporter card should show `opentelemetry`, `otlp`, delivery status, and the failure evidence card should show retry or failure detail when present.

Automated proof:

```bash
cd apps/console && npx playwright test tests/e2e/integration-proof.spec.ts --project=chrome
```
