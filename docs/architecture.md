# Fraud Detection Architecture

This document describes the components and dataflow for the mobile-money fraud detection system implemented in this repository.

Dataflow

Kafka (raw txns) → ConsolidatedFraudDetectionEngine → domain checks → FraudScoreAggregator → Audit log / Review sink

Components
- ConsolidatedFraudDetectionEngine: receives raw transactions, validates, runs domain-specific checks, aggregates the results and writes audit and review records.
- ModelRegistry: central place to load and hot-swap champion/challenger ONNX/joblib models.
- FeatureStore: facade to compute feature vectors using the shared `ml/features.py` functions. Supports fast snapshots for serving.
- Fraud checks: pluggable checks implementing the `FraudCheck` interface. Implementations include:
  - `MLFraudScorer`: calls the champion model (and challenger in shadow) and logs both scores in the audit record.
  - `VelocityDetector`: adaptive velocity detector using per-customer baselining.
  - `SimSwapCorrelator`: flags high-value txns after a recent SIM swap.
  - `NightTransactionFlagger`: soft signal for off-hours activity based on customer local time.
  - `MuleAccountCorrelator`: detects receivers that get funds from many previously-unconnected senders.
- FraudScoreAggregator: weighted combination of check outputs plus an interaction layer that boosts scores when specific check combos fire (e.g., velocity + sim_swap).
- CircuitBreaker: small utility to fail fast when dependencies are failing repeatedly.
- Batch reconciliation: offline job to re-score previously-scored transactions and flag divergences.

Design notes
- The `FeatureStore` reuses `ml/features.py` functions so training and serving compute identical features.
- The `ModelRegistry` loads a champion model into memory and supports a challenger which is scored in shadow.
- The aggregator exposes a clear explanation in the audit log including which interactions contributed a boost.
