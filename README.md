# M-Pesa Fraud Anomaly Detection System

A production-grade real-time fraud detection engine for M-Pesa mobile money transactions, combining rule-based and machine learning approaches with multi-domain orchestration, circuit breaker resilience, and comprehensive audit logging.

This folder is the standalone fraud detection component for the broader M-Pesa streaming platform. It contains the scoring engine, rule checks, ML artifacts, dashboards, deployment assets, and operational documentation used for local testing, staging validation, and deployment workflows.

## Repository Notes

- This folder is intended to be used as an independent repository for fraud anomaly detection work.
- Main entry points include the API service, scoring engine, dashboard app, and Docker Compose setup.
- Typical validation steps include running unit and integration tests, exercising the API locally, and confirming staging pipeline health.

## Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL 13+
- Redis (optional, for feature caching)

### Installation

```bash
cd mpesa_safaricom/fraud_anomaly_detection
pip install -r requirements.txt
```

### Running Tests

```bash
PYTHONPATH=../real_time_transaction_streaming:..:.  \
  python -m pytest tests/ \
    --cov=. \
    --cov-report=html \
    -v
```

Coverage: **48%** (1991 statements) across 30 passing tests.

### Training the ML Model

```bash
python ml/train_model.py \
  --data ml/synthetic_transactions.parquet \
  --output-dir models/run_$(date +%Y-%m-%d_%H) \
  --imbalance-method balanced \
  --sample-size 100
```

Generates calibrated classifier, model card, and optional SHAP explanations.

## System Architecture

The fraud detection engine operates at three layers:

1. **Transaction-Level Checks** (velocity, SIM swap, night hours, mule accounts)
2. **ML-Based Scoring** (HistGradientBoosting + Calibrated Probabilities)
3. **Decision Aggregation** (weighted scoring + circuit breaker + audit logging)

```
Incoming Transaction
    ↓
[Schema Validation] → DLQ (invalid)
    ↓
[Velocity Check]
[SIM Swap Correlator]
[Night Hour Flagger]
[Mule Account Detector]
[ML Fraud Scorer]
    ↓
[Aggregator] → Risk Score (0-100)
    ↓
[Circuit Breaker]
    ↓
[Decision + Audit Log]
```

See [docs/architecture.md](docs/architecture.md) for detailed system design.

## Key Modules

| Module | Purpose | Coverage |
|--------|---------|----------|
| `aggregator.py` | Score combination & decision logic | 100% |
| `checks/` | Individual fraud detectors | 78-97% |
| `engine.py` | Orchestration & transaction routing | 31% |
| `config.py` | Configuration schema & defaults | 90% |
| `ml/train_model.py` | Model training & calibration pipeline | Covered |
| `serving/` | Model registry & feature store | 70-100% |

## Configuration

Configuration is managed via `FraudConfig` (Pydantic model in `config.py`). Override defaults:

```python
from config import FraudConfig

config = FraudConfig(
    ml_weight=0.5,
    velocity_threshold=10,
    night_mode_enabled=True,
    circuit_breaker_failure_threshold=5
)
```

See [docs/fraud_detection.md](docs/fraud_detection.md) for all configurable parameters.

## Model Strength

- **Calibration**: Sigmoid-based CalibratedClassifierCV (5-fold CV)
- **Features**: 12 engineered features (Z-scores, velocity, time-based, account patterns)
- **Imbalance Handling**: Class weighting (default) or SMOTE resampling
- **Explainability**: Optional SHAP values (requires `shap` package)

Latest model card: See [docs/model_strength_report.md](docs/model_strength_report.md)

## API Endpoints

Flask-based REST API (see `app.py`):

```bash
# Health check
GET /health

# Score a transaction
POST /score
Content-Type: application/json
{
  "txn_id": "TXN_001",
  "msisdn": "254712345678",
  "amount": 5000,
  "timestamp": "20260101120000"
}

# Metrics
GET /metrics
```

## Deployment

See [docs/deployment_runbook.md](docs/deployment_runbook.md) for:
- Docker setup
- Kubernetes manifests
- Database migrations
- Model deployment procedures

### Rollback Procedures

If issues occur, see [docs/rollback_procedures.md](docs/rollback_procedures.md).

## Monitoring & Operations

- **Metrics**: Prometheus client (latency, scores, check triggers)
- **Logs**: JSON formatted with context
- **Audit Trail**: Immutable transaction scoring decisions
- **Operations Calendar**: See [docs/operations_calendar.md](docs/operations_calendar.md)

## Contributing

1. Write tests first (coverage target: 80%+)
2. Update `CHANGELOG.md` with changes
3. Run full test suite before submitting
4. Document ADRs for significant changes (see [docs/adr/](docs/adr/))

## Documentation Index

- [Architecture](docs/architecture.md) — System design & components
- [Fraud Detection Config](docs/fraud_detection.md) — Check configurations & model details
- [Integration Notes](docs/integration_notes.md) — Connecting to upstream/downstream systems
- [Model Strength Report](docs/model_strength_report.md) — Latest ML model metrics
- [Ingestion Runbook](docs/ingestion_runbook.md) — Data pipeline operations
- [Deployment Runbook](docs/deployment_runbook.md) — Production deployment steps
- [Rollback Procedures](docs/rollback_procedures.md) — Emergency recovery
- [Operations Calendar](docs/operations_calendar.md) — Key dates & maintenance windows
- [Synthetic Data Notes](docs/synthetic_data_notes.md) — Test data generation
- [Onboarding](docs/onboarding.md) — New team member checklist
- [Data Lineage](docs/data_lineage.md) — Feature & data flow tracing
- [Glossary](docs/glossary.md) — Terms & definitions
- [ADRs](docs/adr/) — Architecture Decision Records

## License

Proprietary — M-Pesa / Safaricom.

## Support

For issues or questions, contact the fraud detection platform team.
