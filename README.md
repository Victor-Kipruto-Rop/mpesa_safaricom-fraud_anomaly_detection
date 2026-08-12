# M-Pesa Fraud Anomaly Detection System

A production-grade, real-time fraud detection engine for M-Pesa mobile money transactions. It combines rule-based checks with machine learning scoring, multi-domain orchestration, circuit breaker resilience, and full audit logging.

This is the standalone fraud detection component of the broader M-Pesa streaming platform. It contains the scoring engine, rule checks, ML artifacts, dashboards, deployment assets, and operational docs for local testing, staging validation, and deployment.

Main entry points: the API service, scoring engine, dashboard app, and Docker Compose setup. Validate changes by running the unit/integration test suite, exercising the API locally, and confirming staging pipeline health.

## Quick Start

**Prerequisites:** Python 3.10+, PostgreSQL 13+, Redis (optional — feature caching)

**Install:**
```bash
cd mpesa_safaricom/fraud_anomaly_detection
pip install -r requirements.txt
```

**Run tests:**
```bash
PYTHONPATH=../real_time_transaction_streaming:..:. \
  python -m pytest tests/ --cov=. --cov-report=html -v
```
Current coverage: **48%** (1,991 statements, 30 passing tests).

**Train the ML model:**
```bash
python ml/train_model.py \
  --data ml/synthetic_transactions.parquet \
  --output-dir models/run_$(date +%Y-%m-%d_%H) \
  --imbalance-method balanced \
  --sample-size 100
```
Produces a calibrated classifier, a model card, and optional SHAP explanations.

## Architecture

The engine scores each transaction in three layers:

1. **Transaction-level checks** — velocity, SIM swap, night-hour activity, mule accounts
2. **ML scoring** — HistGradientBoosting with calibrated probabilities
3. **Decision aggregation** — weighted scoring, circuit breaker, audit logging

```
Incoming Transaction
    │
    ▼
Schema Validation ──► DLQ (invalid)
    │
    ▼
Velocity Check · SIM Swap Correlator · Night Hour Flagger
Mule Account Detector · ML Fraud Scorer
    │
    ▼
Aggregator ──► Risk Score (0–100)
    │
    ▼
Circuit Breaker
    │
    ▼
Decision + Audit Log
```

Full design details: [docs/architecture.md](docs/architecture.md)

## Key Modules

| Module | Purpose | Coverage |
|---|---|---|
| `aggregator.py` | Score combination and decision logic | 100% |
| `checks/` | Individual fraud detectors | 78–97% |
| `engine.py` | Orchestration and transaction routing | 31% |
| `config.py` | Configuration schema and defaults | 90% |
| `ml/train_model.py` | Model training and calibration pipeline | Covered |
| `serving/` | Model registry and feature store | 70–100% |

## Configuration

Managed via `FraudConfig`, a Pydantic model in `config.py`:

```python
from config import FraudConfig

config = FraudConfig(
    ml_weight=0.5,
    velocity_threshold=10,
    night_mode_enabled=True,
    circuit_breaker_failure_threshold=5
)
```

Full parameter reference: [docs/fraud_detection.md](docs/fraud_detection.md)

## Model

- **Calibration:** sigmoid-based `CalibratedClassifierCV`, 5-fold CV
- **Features:** 12 engineered features (Z-scores, velocity, time-based, account patterns)
- **Class imbalance:** class weighting by default, or SMOTE resampling
- **Explainability:** optional SHAP values (requires the `shap` package)

Latest metrics: [docs/model_strength_report.md](docs/model_strength_report.md)

## API

Flask REST API, defined in `app.py`:

```bash
GET  /health              # health check
GET  /metrics             # Prometheus metrics

POST /score                # score a transaction
Content-Type: application/json
{
  "txn_id": "TXN_001",
  "msisdn": "254712345678",
  "amount": 5000,
  "timestamp": "20260101120000"
}
```

## Deployment

Docker, Kubernetes manifests, database migrations, and model deployment procedures: [docs/deployment_runbook.md](docs/deployment_runbook.md)

Emergency recovery: [docs/rollback_procedures.md](docs/rollback_procedures.md)

## Monitoring & Operations

- **Metrics:** Prometheus client (latency, scores, check triggers)
- **Logs:** JSON-formatted, with context
- **Audit trail:** immutable transaction scoring decisions
- **Maintenance windows:** [docs/operations_calendar.md](docs/operations_calendar.md)

## Contributing

1. Write tests first — target 80%+ coverage
2. Update `CHANGELOG.md`
3. Run the full test suite before submitting
4. Document ADRs for significant changes ([docs/adr/](docs/adr/))

## Documentation Index

| Doc | Covers |
|---|---|
| [Architecture](docs/architecture.md) | System design & components |
| [Fraud Detection Config](docs/fraud_detection.md) | Check configurations & model details |
| [Integration Notes](docs/integration_notes.md) | Connecting upstream/downstream systems |
| [Model Strength Report](docs/model_strength_report.md) | Latest ML model metrics |
| [Ingestion Runbook](docs/ingestion_runbook.md) | Data pipeline operations |
| [Deployment Runbook](docs/deployment_runbook.md) | Production deployment steps |
| [Rollback Procedures](docs/rollback_procedures.md) | Emergency recovery |
| [Operations Calendar](docs/operations_calendar.md) | Key dates & maintenance windows |
| [Synthetic Data Notes](docs/synthetic_data_notes.md) | Test data generation |
| [Onboarding](docs/onboarding.md) | New team member checklist |
| [Data Lineage](docs/data_lineage.md) | Feature & data flow tracing |
| [Glossary](docs/glossary.md) | Terms & definitions |
| [ADRs](docs/adr/) | Architecture Decision Records |

## License

Proprietary — M-Pesa / Safaricom.

## Support

Contact the fraud detection platform team.
