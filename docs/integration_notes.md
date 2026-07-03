# Integration Notes

## Upstream Systems

### Real-Time Transaction Streaming (`../real_time_transaction_streaming/`)

**Interface**: `app.services.fraud_detection_service.StreamingFraudDetectionService`

```python
from app.services.fraud_detection_service import StreamingFraudDetectionService

service = StreamingFraudDetectionService(config)
decision = service.score_transaction(transaction_dict)
```

**Expected Input Format**:

```json
{
  "TransID": "TXN_001",
  "MSISDN": "254712345678",
  "TransAmount": "5000.00",
  "TransTime": "20260101120000",
  "BusinessShortCode": "123456",
  "AccountReference": "REF123"
}
```

**Output Format**:

```json
{
  "decision": "BLOCK",
  "score": 85.2,
  "checks": {
    "velocity": {"score": 70, "triggered": true},
    "ml": {"score": 90, "confidence": 0.95},
    "night_flag": {"score": 0, "triggered": false}
  },
  "audit_log_id": "ALG_20260101_001",
  "timestamp": "2026-01-01T12:00:00Z"
}
```

## Downstream Systems

### Fraud Detection Unified (`../fraud_detection_unified/`)

**Interface**: `ConsolidatedFraudDetectionEngine`

Multi-domain orchestration combining M-Pesa fraud detection with other payment domains:

```python
from fraud_detection_unified.engine import ConsolidatedFraudDetectionEngine

engine = ConsolidatedFraudDetectionEngine()
result = engine.score_multi_domain_transaction(
    domain="mpesa",
    transaction_data=txn_dict
)
```

### Database Persistence

**Tables** (PostgreSQL):
- `fraud_transaction_scores` (decision log)
- `fraud_audit_logs` (detailed decision context)
- `fraud_alert_history` (escalation tracking)

**Connection**:

```python
from sqlalchemy import create_engine

engine = create_engine(os.getenv("DATABASE_URL"))
```

## Webhook Integration

**Endpoint**: `POST /fraud/webhook/c2b-confirmation`

Receives C2B (Customer-to-Business) STK push confirmations for real-time scoring.

**Payload**:

```json
{
  "Body": {
    "stkCallback": {
      "MerchantRequestID": "29115-34620561-1",
      "CheckoutRequestID": "ws_CO_DMZ_123456789_01012626101234_34620561",
      "ResultCode": 0,
      "ResultDesc": "The service request has been accepted successfully.",
      "CallbackMetadata": {
        "Item": [
          {"Name": "Amount", "Value": 1},
          {"Name": "MpesaReceiptNumber", "Value": "LHG31H500V"},
          {"Name": "ResponseCode", "Value": "0"}
        ]
      }
    }
  }
}
```

**Response**:

```json
{
  "status": "processed",
  "fraud_decision": "ACCEPT",
  "metrics_recorded": true
}
```

## Feature Dependencies

### Feature Store (`serving/feature_store.py`)

Caches computed features to avoid recomputation:

```python
from serving.feature_store import FeatureStore

store = FeatureStore()
features = store.get_features(
    msisdn="254712345678",
    lookback_days=7
)
```

**Cached Features**:
- Z-score of amount vs. user history
- Velocity counts (24h, 7d, 30d)
- Night hour flag
- Device change flag
- Account age

## Error Handling

### Schema Validation Failures

Invalid transactions are automatically routed to DLQ:

```python
from schema_validator import SchemaValidator

is_valid, error = SchemaValidator.validate(payload)
if not is_valid:
    dlq_msg = SchemaValidator.format_dlq_message(
        raw_payload=payload,
        error=error,
        topic="mpesa-transactions"
    )
    # Send to DLQ topic for later replay
```

### Circuit Breaker Engagement

If fraud detection becomes unstable (too many failures):

```python
from circuit_breaker import CircuitBreaker

breaker = CircuitBreaker(failure_threshold=5)
if breaker.is_open():
    # Fail safe: block all transactions or revert to rule-only
    decision = "BLOCK"  # or call_fallback()
```

## Configuration Propagation

Updates to `config.yaml` are automatically loaded by `ConfigManager` (hot-reload every 30s):

```python
from config_manager import ConfigManager

manager = ConfigManager(config_path="config.yaml")
# Manager watches file, reloads on change
new_config = manager.get_config()
```

No service restart needed.

## Monitoring & Alerting

### Metrics Exposed

Prometheus metrics at `GET /metrics`:

```
fraud_detection_checks_total{check="velocity", decision="block"}
fraud_detection_latency_seconds (histogram)
fraud_detection_scores (gauge)
```

### Log Ingestion

Structured JSON logs for ELK/Splunk:

```json
{
  "timestamp": "2026-01-01T12:00:00Z",
  "level": "INFO",
  "message": "Transaction scored",
  "txn_id": "TXN_001",
  "decision": "BLOCK",
  "check_scores": {
    "velocity": 70,
    "ml": 90
  }
}
```

## Performance SLAs

| Operation | SLA | Notes |
|-----------|-----|-------|
| Single check execution | <50ms | Cached features |
| Full pipeline | <100ms | All checks in parallel |
| Model inference | <20ms | CPU-based, no GPU required |
| Feature computation | <30ms | Cached most of the time |

## Backward Compatibility

Model versions are tracked in the audit log. To rollback:

1. Update `config.yaml` to point to older model
2. Restart service (or wait for config hot-reload)
3. New transactions use old model
4. No re-scoring of historical decisions needed
