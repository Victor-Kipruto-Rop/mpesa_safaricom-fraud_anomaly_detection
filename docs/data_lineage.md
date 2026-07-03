# Data Lineage

## Transaction Flow Through System

```
┌─────────────────────────────────────────────────────────┐
│  Upstream System: Real-Time Transaction Streaming        │
│  (real_time_transaction_streaming/app/)                 │
└─────────────────────────────────────────────────────────┘
                          ↓
            Raw Transaction JSON
            {TransID, MSISDN, Amount, Time, ...}
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Fraud Detection Service                                 │
│  1. Schema Validation (schema_validator.py)             │
│  2. Feature Engineering (ml/features.py)                │
│  3. Multi-Check Evaluation (checks/*.py)                │
│  4. Score Aggregation (aggregator.py)                   │
│  5. Audit Logging (audit_log.py)                        │
└─────────────────────────────────────────────────────────┘
                          ↓
     Fraud Detection Decision + Audit Context
            (ACCEPT | REVIEW | BLOCK)
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Downstream Systems                                      │
│  • Database (fraud_transaction_scores table)            │
│  • Downstream Frauds System (fraud_detection_unified)   │
│  • Webhook Confirmations (C2B STK push tracking)        │
└─────────────────────────────────────────────────────────┘
```

---

## Feature Lineage

### Input Features (Raw Transaction)

```
Transaction JSON
    ├─ TransID: str (Identifier)
    ├─ MSISDN: str (Phone number)
    ├─ TransAmount: numeric (Amount in KES)
    ├─ TransTime: str (YYYYMMDDHHmmss)
    ├─ BusinessShortCode: str (Merchant code)
    └─ AccountReference: str (Optional, user's reference)
```

### Computed Features (Feature Engineering)

**Location**: `ml/features.py`

```
Input Transaction
    ├─ amount_z_score
    │   └─ Calculation: (amount - user_avg_amount) / user_std_amount
    │   └─ Window: Last 30 days
    │   └─ Handling: If no history, z_score = 0
    │
    ├─ transaction_velocity_24h
    │   └─ Calculation: Count of txns by MSISDN in last 24h
    │   └─ Source: Feature store cache (updated every 15 min)
    │   └─ Cache miss: Recompute from audit logs
    │
    ├─ unusual_hour_flag
    │   └─ Calculation: Is timestamp between 00:00-06:00?
    │   └─ Timezone-aware (configurable per region)
    │
    ├─ device_change_flag
    │   └─ Calculation: Is device ID different from last txn?
    │   └─ Requires: Device tracking (optional)
    │
    └─ (8 more features)
```

### Feature Storage

**Feature Store** (`serving/feature_store.py`):
- Caches computed features to avoid recomputation
- TTL: 15 minutes (auto-refresh)
- Backend: In-memory dict (can be upgraded to Redis)

**Model Features** (12 total for ML model):
```
X_train shape: (N_samples, 12)
  ├─ Numerical: z_score, velocity_24h, velocity_7d, velocity_30d, device_flag, hour_flag, ...
  ├─ Categorical (one-hot): region (11 regions)
  └─ Target: y_train = [0 (legitimate) | 1 (fraud)]
```

---

## Model Artifact Lineage

### Training

```
ml/synthetic_transactions.parquet (or real labeled data)
    ↓
[Feature Engineering] → X_train, y_train
    ↓
[Train/Val/Test Split]
    ├─ Train: 70% (time-aware entity-safe split)
    ├─ Val: 15%
    └─ Test: 15%
    ↓
[HistGradientBoostingClassifier Training]
    └─ base_model
    ↓
[CalibratedClassifierCV - 5 Fold]
    └─ calibrated_model (with probability calibration)
    ↓
[Model Serialization]
    └─ mobile_money_fraud_calibrated.joblib
    ↓
[Model Card Generation]
    └─ MODEL_CARD.md (metrics, calibration, SHAP summary)
```

### Serving

```
models/run_YYYY-MM-DD_HH/mobile_money_fraud_calibrated.joblib
    ↓
[Model Registry Load] (serving/model_registry.py)
    ├─ Lazy load on first use
    ├─ Cache in memory
    └─ Hot-reload on model_path config change
    ↓
[Inference]
    ├─ Input: 12-dimensional feature vector
    ├─ Output: Probability [0, 1]
    └─ Scaling: risk_score = probability * 100
```

### Versioning

Model versions tracked in:
1. **Audit Log**: Each decision records `model_version` used
2. **Git Tag**: `v2026.01.0` corresponds to model trained on Jan 2026 data
3. **Config**: `config.yaml` specifies MODEL_PATH

Example:
```
Transaction TXN_001
    ↓ Scored by model: mobile_money_fraud_calibrated.joblib
    ↓ Model version: 2026.01.0 (trained Jan 1, 2026)
    ↓ Audit log records: decision, model_version, features used
```

---

## Check Score Lineage

### Individual Check Scores

```
Transaction
    ├─ VelocityDetector
    │   ├─ Input: MSISDN, timestamp
    │   ├─ Computation: count(txns) in last 24h
    │   ├─ Output: CheckResult(score=50, triggered=true/false)
    │   └─ Example: 12 txns in 24h → score=120 (capped at 100)
    │
    ├─ SimSwapCorrelator
    │   ├─ Input: MSISDN, device_id, timestamp
    │   ├─ Computation: Are other MSISDNs sending from same device?
    │   ├─ Output: CheckResult(score=0-100, triggered=true/false)
    │   └─ Example: 3 other accounts from same device → score=80
    │
    ├─ NightTransactionFlagger
    │   ├─ Input: timestamp
    │   ├─ Computation: Is time in [00:00, 06:00]?
    │   ├─ Output: CheckResult(score=0 or 30, triggered=true/false)
    │   └─ Example: 02:30 AM → score=30, triggered=true
    │
    ├─ MuleAccountCorrelator
    │   ├─ Input: MSISDN, amount, timestamp
    │   ├─ Computation: Is account rapidly forwarding funds?
    │   ├─ Output: CheckResult(score=0-100, triggered=true/false)
    │   └─ Example: 5 forwards in 1 hour → score=90
    │
    └─ MLFraudScorer
        ├─ Input: 12 engineered features
        ├─ Computation: calibrated_model.predict_proba(X) → [0, 1]
        ├─ Output: CheckResult(score=prob*100, confidence=prob)
        └─ Example: prob=0.92 → score=92, confidence=0.92
```

### Aggregation

```
All Check Results
    ├─ scores: [50, 0, 30, 0, 92]
    ├─ rule_weight: 0.3
    ├─ ml_weight: 0.7
    │
    └─ Aggregation Logic:
        rule_score = mean([50, 0, 30, 0]) = 20
        ml_score = 92
        combined_score = (20 * 0.3) + (92 * 0.7) = 70.4
        ↓
        Decision: BLOCK (combined_score > block_threshold=70)
        ↓
        Final Output:
        {
          "decision": "BLOCK",
          "score": 70.4,
          "checks": {
            "velocity": 50,
            "sim_swap": 0,
            "night_flag": 30,
            "mule": 0,
            "ml": 92
          }
        }
```

---

## Audit Log Lineage

### What Gets Logged

```
Audit Log Entry
    ├─ timestamp: 2026-01-01T12:00:00Z
    ├─ txn_id: TXN_001
    ├─ msisdn: 254712345678
    ├─ amount: 5000
    ├─ decision: BLOCK
    ├─ risk_score: 70.4
    ├─ check_scores: {velocity: 50, ml: 92, ...}
    ├─ model_version: v2026.01.0
    ├─ features_computed: [z_score, velocity_24h, ...]
    ├─ circuit_breaker_status: CLOSED
    └─ audit_log_id: ALG_20260101_001 (unique ID for traceability)
```

### Storage

**Database Table**: `fraud_audit_logs`
```sql
CREATE TABLE fraud_audit_logs (
    audit_log_id VARCHAR PRIMARY KEY,
    timestamp TIMESTAMP,
    txn_id VARCHAR,
    msisdn VARCHAR,
    decision VARCHAR (ENUM),
    risk_score FLOAT,
    check_scores JSONB,
    model_version VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Retention Policy

- **Hot**: Last 7 days (queryable, fast)
- **Warm**: 7 days - 90 days (compressed, slower queries)
- **Cold**: 90+ days (archived to S3, requires restore)

---

## Schema Validation & DLQ Lineage

### Invalid Transaction Flow

```
Raw Transaction JSON
    ↓
[SchemaValidator.validate()]
    ├─ Check: All required fields present?
    ├─ Check: All types correct?
    ├─ Check: All values in valid range?
    │
    ├─ If VALID → Continue to fraud checks
    │
    └─ If INVALID → DLQ Routing
        ├─ Format DLQ message with:
        │   ├─ Original payload
        │   ├─ Error message
        │   ├─ Topic/Partition/Offset (if from Kafka)
        │   └─ Timestamp
        │
        └─ Route to Dead Letter Queue
            └─ For later inspection & replay
```

### DLQ Message Example

```json
{
  "original_payload": {
    "TransID": "TXN_001",
    "MSISDN": "INVALID_MSISDN"
  },
  "schema_error": "MSISDN must match pattern 254XXXXXXXXX",
  "original_topic": "mpesa-transactions",
  "partition": 2,
  "offset": 1234567,
  "timestamp": 1672531200000
}
```

---

## Dependency Graph

```
External Libs
    ├─ pandas (data manipulation)
    ├─ numpy (numerical ops)
    ├─ scikit-learn (ML models)
    ├─ pydantic (config validation)
    ├─ flask (API server)
    └─ prometheus_client (metrics)
          ↓
    Fraud Detection Modules
          │
    ├─ config.py (configuration schema)
    ├─ schema_validator.py (input validation)
    │
    ├─ ml/
    │   ├─ features.py (feature engineering)
    │   └─ train_model.py (training pipeline)
    │
    ├─ checks/
    │   ├─ base.py (abstract base)
    │   ├─ velocity_detector.py
    │   ├─ sim_swap_correlator.py
    │   ├─ night_flagger.py
    │   ├─ mule_correlator.py
    │   └─ ml_scorer.py (uses trained model)
    │
    ├─ aggregator.py (combines check scores)
    ├─ circuit_breaker.py (safety mechanism)
    ├─ engine.py (orchestration)
    ├─ serving/model_registry.py (model loading)
    └─ app.py (Flask API) → produces decisions
              ↓
    Downstream Systems
    ├─ Database (fraud_transaction_scores)
    ├─ fraud_detection_unified (multi-domain)
    └─ External Webhooks (C2B confirmations)
```

---

## Performance & Caching Strategy

### Cached Data

| Data | TTL | Source | Purpose |
|------|-----|--------|---------|
| Feature vectors | 15 min | Feature store | Avoid recomputation |
| Model weights | Forever (restart) | joblib | ML inference |
| Config | 30 sec | config.yaml | Hot-reload settings |
| Transaction history | 24 hours | Audit logs | Velocity detection |

### Data Dependencies

```
Transaction T1 arrives
    ↓ Needs features
    ├─ Fresh features? → Use cache
    └─ Stale features? → Recompute from audit logs
    ↓ Depends on
    ├─ Previous transactions (last 24h for velocity)
    ├─ Account history (z-score baseline)
    └─ Device linkage (SIM swap detection)
    ↓
Transaction T2 arrives (5 sec later)
    ├─ Can reuse cached features from T1
    └─ Saves 30-50ms computation
```

---

## See Also

- [architecture.md](architecture.md) — System design
- [fraud_detection.md](fraud_detection.md) — Configuration details
- [model_strength_report.md](model_strength_report.md) — Model metrics
