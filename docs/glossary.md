# Glossary

## Fraud Detection Terms

### A

**Audit Log**
- Immutable record of every transaction scored by the fraud detection system
- Contains: decision, scores from each check, model version, timestamp
- Used for: compliance, forensics, trend analysis
- Retention: 90+ days (configurable)

**Aggregation / Aggregator**
- Process of combining multiple fraud check scores into a single decision
- Weights rule-based checks (velocity, SIM swap, etc.) vs. ML score
- Produces: ACCEPT | REVIEW | BLOCK decision
- See: `aggregator.py`

### B

**Baseline**
- Historical user transaction pattern (amount, frequency, time of day)
- Used to detect anomalies (z-score, velocity violations)
- Computed from: last 30-90 days of transactions

**Block / Blocked Transaction**
- Decision to reject a transaction due to high fraud risk
- Risk score > `block_threshold` (default: 70)
- Prevents transaction from completing
- User may appeal via review process

### C

**Calibration**
- Process of adjusting ML model output probabilities to match true likelihood
- Method: Sigmoid curve fitting (Platt scaling)
- Ensures: 80% fraud probability means ~80% of transactions are actually fraud
- Without calibration: raw model may output 0.92 prob, but 60% are actually fraud

**Circuit Breaker**
- Safety mechanism that stops fraud detection when system is degraded
- States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing recovery)
- Prevents cascading failures
- See: `circuit_breaker.py`

**Confidence**
- Certainty level of a fraud check's output (0-1 scale)
- Example: ML scorer confidence=0.92 means high certainty prediction
- Lower confidence → may override with more conservative decision

### D

**Dead Letter Queue (DLQ)**
- Repository for transactions that fail schema validation
- Stored for later inspection & replay
- Prevents data loss on validation errors
- See: `schema_validator.py`

**Decision**
- Final fraud determination: ACCEPT | REVIEW | BLOCK
- Based on aggregated risk score + circuit breaker status
- Logged immutably in audit logs

### E

**Entity-Safe Split**
- Train/val/test split that keeps all transactions from same user in same fold
- Prevents data leakage (model shouldn't see user in both train & test)
- Time-ordered: train (early), val (middle), test (latest)

### F

**False Negative (FN)**
- Fraudulent transaction incorrectly marked ACCEPT
- Risk: Financial loss, customer frustration with fraud liability
- Measured via: FNR (False Negative Rate) = FN / (FN + TP)

**False Positive (FP)**
- Legitimate transaction incorrectly marked BLOCK
- Risk: Customer friction, complaints, abandoned transactions
- Measured via: FPR (False Positive Rate) = FP / (FP + TN)

**Fraud Pattern**
- Characteristic sequence or signature of fraudulent behavior
- Examples: Velocity abuse, SIM swap ring, mule account chain, night hour spike
- Detection: Rule-based checks + ML model

### H

**Hot Reload**
- Feature allowing configuration changes without restarting service
- Interval: Every 30 seconds, config manager checks for file changes
- Benefit: No downtime, immediate effect on new transactions

### M

**Mule Account**
- Account used to forward stolen funds to obscure their origin
- Typically: Account A (fraud victim) → Mule B → Mule C → Cash out
- Detection: MuleAccountCorrelator tracks rapid fund forwarding chains

**Model Card**
- Document describing ML model: architecture, training data, calibration, metrics
- Includes: Dataset size, feature list, performance metrics, fairness notes
- Location: Generated in `models/run_YYYY-MM-DD_HH/MODEL_CARD.md`

### N

**Night Hour**
- Time window (default: 00:00-06:00) when users are typically inactive
- Fraudsters often operate at night when victims won't notice
- Configurable per region/timezone

### O

**On-Call**
- Engineer responsible for responding to production incidents (phone/Slack)
- Rotation: Weekly, 24/7 coverage
- Responsibilities: Monitoring alerts, incident response, escalation

### P

**Probability Calibration**
- See: **Calibration**

### R

**Review / Reviewed Transaction**
- Decision state: Score between accept & block thresholds
- Requires: Manual inspection by fraud analyst
- Example: risk_score=50 → escalated for human review (not auto-blocked)

**Risk Score**
- Numerical output (0-100) representing fraud probability
- 0: Completely legitimate
- 100: Definitely fraudulent
- Thresholds: ACCEPT < 30, REVIEW 30-70, BLOCK > 70 (configurable)

### S

**SIM Swap**
- Attack: Fraudster convinces MNO to transfer victim's phone number to new SIM
- Result: Fraudster can receive victim's SMS/calls, intercept OTP
- Detection: SimSwapCorrelator detects multiple accounts accessed from same device

**SMOTE (Synthetic Minority Over-sampling Technique)**
- Technique to handle class imbalance in training
- Creates synthetic fraud examples by interpolating between existing frauds
- Alternative to class weighting

### T

**Transaction**
- Single M-Pesa payment: send funds from MSISDN A to business/person B
- Attributes: TransID, MSISDN, amount, timestamp, merchant code

**True Negative (TN)**
- Legitimate transaction correctly marked ACCEPT
- Good outcome: No false alarm

**True Positive (TP)**
- Fraudulent transaction correctly marked BLOCK
- Good outcome: Fraud prevented

### V

**Velocity**
- Count of transactions from same account in time window
- Example: 10 transactions in 24 hours = high velocity
- Detection: VelocityDetector triggers when count > threshold

### Z

**Z-Score**
- Statistical measure of how far a value deviates from mean
- Formula: z = (x - μ) / σ
- Usage: amount_z_score = how unusual is this transaction amount for this user?
- Example: z=3 means amount is 3 standard deviations above user average (anomalous)

---

## System Architecture Terms

### Check
- Individual fraud detection rule or model
- Interface: `FraudCheck` base class
- Examples: VelocityDetector, MLFraudScorer
- Output: `CheckResult(score, triggered, confidence)`

### Configuration Schema
- Pydantic model defining all system parameters
- Location: `config.py`
- Features: Validation, type hints, default values
- Hot-reloadable via `ConfigManager`

### Feature Engineering
- Process of computing 12 numerical features from raw transaction
- Features capture: Amounts (z-score), velocity, time-of-day, device info
- Location: `ml/features.py`

### Feature Store
- Cache of computed features to avoid recomputation
- TTL: 15 minutes (auto-refresh)
- Location: `serving/feature_store.py`

### ML Model
- HistGradientBoostingClassifier trained on labeled transactions
- Predicts: Probability that transaction is fraudulent [0, 1]
- Calibrated: Sigmoid curve ensures probabilities match true rates
- Location: `models/run_YYYY-MM-DD_HH/mobile_money_fraud_calibrated.joblib`

### Model Registry
- Service that loads, caches, and versionsML models
- Handles: Model loading, hot-reload on version change, fallback
- Location: `serving/model_registry.py`

### PYTHONPATH
- Environment variable telling Python where to import modules from
- Set to: `real_time_transaction_streaming:..:.` (allows relative imports)
- Required for: Running tests, scripts with proper module resolution

---

## Operations Terms

### Deployment
- Process of moving code/models from dev to staging to production
- Includes: Building Docker image, pushing to registry, rolling out to K8s
- Rollback: Quick revert if deployment is bad

### Incident
- Production issue requiring urgent response
- Examples: High error rate, model crash, latency spike
- Process: Detect → Triage → Rollback (if needed) → RCA → Prevention

### Monitoring
- Continuous observation of system health via metrics & logs
- Tools: Prometheus (metrics), ELK (logs), Grafana (dashboards)
- Alerts: Triggered if error rate > 1% or latency > 200ms

### RCA (Root Cause Analysis)
- Investigation of incident to understand why it happened
- Output: Document identifying root cause + prevention measures
- Timing: Within 24 hours of incident resolution

### SLA (Service Level Agreement)
- Contractual uptime/latency commitment
- Examples: 99.5% uptime, < 200ms P95 latency
- Measured: Monthly, reported to stakeholders

---

## See Also

- [architecture.md](architecture.md) — System components
- [fraud_detection.md](fraud_detection.md) — Detailed config
- [data_lineage.md](data_lineage.md) — Data flow & dependencies
