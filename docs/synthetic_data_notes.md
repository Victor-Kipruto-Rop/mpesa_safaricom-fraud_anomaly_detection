# Synthetic Data Notes

## Overview

Synthetic transaction data is generated for model training, testing, and demonstrations without using real customer data.

**Generator**: `ingestion/generate_fraud_data.py`

## Data Generation Strategy

### Transaction Volume

```python
N_TRANSACTIONS = 10_000  # Default
N_FRAUD_TRANSACTIONS = 1_000  # 10% fraud rate (realistic baseline)
```

Adjust via:
```bash
python ingestion/generate_fraud_data.py --n-transactions 50000 --fraud-rate 0.05
```

### Feature Distribution

#### Amount
- **Legitimate**: Log-normal (μ=6, σ=1), range: 100-50,000 KES
- **Fraudulent**: Bimodal (small: 1,000-5,000 KES, large: 50,000-500,000 KES)

**Rationale**: Fraudsters often test with small amounts first, then attempt large transfers.

#### Time of Day
- **Legitimate**: Uniform distribution across 24 hours (users active anytime)
- **Fraudulent**: Concentrated in night hours (00:00-06:00) - 60% of fraud

**Rationale**: Criminals prefer operating when victim is unlikely to notice.

#### Account Behavior
- **Normal Users**: 2-5 transactions/day on average
- **Fraud Rings**: 10+ transactions/hour (multiple accounts in sequence)

#### Location (Simulated via MSISDN prefix)
- 254712 (Nairobi), 254713 (Coastal), 254722 (Rift Valley), etc.
- **Fraud Concentration**: Nairobi & Coastal regions (60% of synthetic fraud)

### Fraud Patterns

#### Pattern 1: Velocity Abuse
```
Time    | MSISDN      | Amount | Desc
--------|-------------|--------|----------
00:15   | 254712001   | 5,000  | TXN 1
00:18   | 254712001   | 8,000  | TXN 2
00:22   | 254712001   | 12,000 | TXN 3 ← Unusual (normal user = 2-5/day)
```

**Detection**: VelocityDetector triggers at TXN 3 (velocity_threshold=10)

#### Pattern 2: SIM Swap Ring
```
Device ID | MSISDN A | Time 1    | → Transfer to MSISDN B
Device ID | MSISDN B | Time 2    | → Transfer to MSISDN C
Device ID | MSISDN C | Time 3    | → Transfer to safe account
```

**Detection**: SimSwapCorrelator detects chain of txns from same device

#### Pattern 3: Night Hour Fraud
```
User A typically active 09:00-18:00 (work hours)
Transaction at 02:30 → Flagged by NightTransactionFlagger
```

**Detection**: NightFlagger + z-score anomaly

#### Pattern 4: Mule Account Ring
```
Primary account → Mule 1 → Mule 2 → Mule 3 → Cash out
(Funds forwarded through multiple accounts to obscure source)
```

**Detection**: MuleCorrelator identifies rapid chain of forwards

## Generating Custom Data

### Example 1: High-Fraud Scenario (Testing)

```bash
python ingestion/generate_fraud_data.py \
  --n-transactions 5000 \
  --fraud-rate 0.30 \
  --focus-night-hours \
  --output data/high_fraud_sample.parquet
```

**Use Case**: Stress test the ML model (does it handle 30% fraud rate?)

### Example 2: Low-Velocity Scenario (Baseline)

```bash
python ingestion/generate_fraud_data.py \
  --n-transactions 5000 \
  --fraud-rate 0.05 \
  --normal-distribution \
  --output data/baseline_sample.parquet
```

**Use Case**: Train model on realistic (5%) fraud rate

### Example 3: Seasonality Test

```bash
python ingestion/generate_fraud_data.py \
  --n-transactions 10000 \
  --start-date 2025-12-01 \
  --end-date 2026-01-31 \
  --fraud-rate 0.08 \
  --seasonal-boost 1.5 \  # 50% more fraud in Dec-Jan
  --output data/seasonal_sample.parquet
```

**Use Case**: Test if model adapts to seasonal fraud spikes

## Data Schema

Generated parquet files contain:

```python
{
    'txn_id': str,                    # Unique transaction ID
    'msisdn': str,                    # 254712345678 format
    'amount': float,                  # KES
    'timestamp': str,                 # ISO 8601
    'business_short_code': str,       # M-Pesa merchant code
    'account_reference': str,         # User's reference
    'label': int,                     # 0=legitimate, 1=fraud (for training)
    'fraud_pattern': str,             # (optional) 'velocity', 'sim_swap', 'night_hour', 'mule'
    'device_id': str,                 # (optional) For detecting SIM swap rings
}
```

## Training Data Preparation

### Step 1: Generate

```bash
python ingestion/generate_fraud_data.py \
  --n-transactions 100000 \
  --fraud-rate 0.07 \
  --output ml/training_transactions.parquet
```

### Step 2: Validate

```bash
python -c "
import pandas as pd
df = pd.read_parquet('ml/training_transactions.parquet')
print(f'Rows: {len(df)}')
print(f'Fraud rate: {df[\"label\"].mean():.1%}')
print(f'Time range: {df[\"timestamp\"].min()} to {df[\"timestamp\"].max()}')
print(df.head())
"
```

### Step 3: Split & Train

```bash
python ml/train_model.py \
  --data ml/training_transactions.parquet \
  --output-dir models/run_$(date +%Y-%m-%d_%H) \
  --sample-size 200 \
  --imbalance-method balanced
```

## Limitations & Caveats

**⚠️ Synthetic data is NOT representative of real fraud patterns:**

1. **No seasonal trends** (data is uniform across months)
2. **Fraud is too obvious** (large amounts, predictable patterns)
3. **No account linking** (no real customer relationship networks)
4. **No geospatial clusters** (fraud distribution is artificial)
5. **Simplified features** (real fraud uses more nuanced patterns)

**Use Case**: 
- ✅ Model development & testing
- ✅ Load testing
- ✅ Demonstrating capability
- ❌ Measuring real-world performance (requires real data & PIIs handled securely)

## Privacy & Compliance

### No Real Data Used
All phone numbers, amounts, and timestamps are randomly generated.

### Safe to Share
Synthetic data can be:
- Shared with external stakeholders
- Used in demos
- Included in GitHub repo (with appropriate licenses)

### Before Using Real Data
- **PII Handling**: Anonymize or hash phone numbers
- **Data Retention**: Document retention policy
- **Access Control**: Restrict to authorized personnel
- **Encryption**: Encrypt data at rest & in transit
- **Audit Logging**: Track who accessed what, when

## Improving Data Realism

### Option 1: Domain Expert Input
Collaborate with fraud ops to refine fraud patterns:
- What % of fraud is velocity-based vs. other patterns?
- What are typical times when real users are inactive?
- How long do SIM swap attacks typically take?

### Option 2: Hybrid Approach
- Use real transaction amounts & times (after anonymization)
- Simulate labels using fraud ops domain knowledge
- Validate with historical data patterns

### Option 3: Federated Learning
- Train on real data without moving it (data stays with MNO)
- Share only model updates & gradients
- Requires coordination with data governance team

---

## Configuration

Edit `ingestion/generate_fraud_data.py` to adjust:

```python
# Amount distribution
LEGITIMATE_AMOUNT_MU = 6.0          # Log-normal μ
LEGITIMATE_AMOUNT_SIGMA = 1.0       # Log-normal σ
FRAUD_AMOUNT_SMALL_MEAN = 3000      # Small fraud test
FRAUD_AMOUNT_LARGE_MEAN = 100000    # Large fraud

# Timing
NIGHT_HOURS_START = 0               # 00:00
NIGHT_HOURS_END = 6                 # 06:00
FRAUD_NIGHT_PROBABILITY = 0.6       # 60% of fraud at night

# Velocity
NORMAL_USER_TXN_PER_DAY = [2, 5]    # Random choice between 2-5
FRAUD_RING_TXN_PER_HOUR = [10, 20]  # Random choice between 10-20
```

## Testing Checklist

Before deploying a new training dataset:

- [ ] Check row count matches expected
- [ ] Verify fraud rate is as specified (usually 5-10%)
- [ ] Confirm timestamp range is correct
- [ ] Inspect first 100 rows (no obvious duplicates)
- [ ] Run train/val/test split (70/15/15)
- [ ] Train model and verify metrics improve or stay stable
- [ ] Document generation command in README

---

## See Also

- [ml/train_model.py](../ml/train_model.py) — Model training pipeline
- [docs/model_strength_report.md](model_strength_report.md) — Latest model metrics
- [docs/deployment_runbook.md](deployment_runbook.md) — Deploying trained models
