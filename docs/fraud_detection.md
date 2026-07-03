# Fraud Detection: Mobile Money Engine

Architecture, configuration and runbook for the `ConsolidatedFraudDetectionEngine` mobile-money checks.

## Overview

This engine runs pluggable checks (ML, Velocity, SIM-swap, Night flag) and aggregates an explainable score.

## Topics
- Config keys and defaults: see `config.py`
- Redis keys: `mm:velocity:{msisdn}`, `mm:sim_swap:{msisdn}`, `mm:features:{msisdn}`
- Audit log: append-only JSONL files under `fraud_audit/`

## Runbook (common failures)

- Redis down: engine treats Redis checks as degraded, emits `fraud_dependency_failure_total{dependency="redis"}` metric, continues scoring without velocity/sim signals.
- Model corrupt or missing: engine continues rule-based scoring; `fraud_dependency_failure_total{dependency="model"}` increments.
- Config rollback: replace config via config store and call hot-reload; config changes include `config_version`.

## Data flow (Mermaid)
```mermaid
graph LR
  subgraph ingest
    A[mpesa.transactions.raw] --> B[Scoring Engine]
  end
  B --> C[mpesa.transactions.scored]
  B --> D[Audit Log (immutable)]
  B --> E[Review Queue]
```

## Model and training

- Synthetic data generator: `ml/generate_synthetic_transactions.py`
- Feature engineering (shared): `ml/features.py`
- Training script: `ml/train_model.py` (exports joblib and attempts ONNX via `skl2onnx`)
- Model card: `ml/model_card.md`
- Register model: `ml/register_model.py`

Run training locally after installing `requirements-fraud.txt`. The model is synthetic and must be retrained on labeled production data before use in blocking decisions.

