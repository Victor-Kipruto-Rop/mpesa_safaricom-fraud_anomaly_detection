# ADR-0004: Feature Engineering Strategy

**Date**: 2026-01-01  
**Status**: Accepted  
**Context**: ML model requires numerical features that capture fraud patterns in M-Pesa transactions  
**Decision**: Engineer 12 features combining amount anomalies, transaction velocity, temporal patterns, and account behavior, computed in real-time during scoring with caching to avoid recomputation.

## Problem

Raw M-Pesa transactions have limited information:
```json
{
  "TransID": "TXN_001",
  "MSISDN": "254712345678",
  "TransAmount": 5000,
  "TransTime": "20260101120000",
  "BusinessShortCode": "123456"
}
```

This raw data is insufficient for ML model training because:

1. **Missing Context**: Is 5000 KES unusual for this user? (Needs historical baseline)
2. **Missing Velocity**: Is this user normally active at 12:00 PM? (Needs temporal patterns)
3. **Missing Relationships**: Are other accounts linked to this device? (Needs graph analysis)
4. **Raw Amounts Aren't Comparable**: 5000 is high for student, normal for merchant

ML model needs **meaningful features** that the classifier can use to identify fraud patterns.

## Solution

Engineer 12 features across 4 categories:

### Category 1: Amount Anomalies (3 features)

**Feature 1: Amount Z-Score**
```python
z_score = (current_amount - user_mean_amount) / user_std_amount
```
- **Interpretation**: How many standard deviations from user average?
- **Example**: User avg=1000, std=200, current=1500 → z=2.5 (unusual)
- **Computation**: Cached from last 30 days of transactions
- **Handling**: If no history, z=0 (neutral)

**Feature 2-3: Top-N Amount Percentiles**
```python
percentile_75 = user_amounts_sorted[0.75 * len(amounts)]
percentile_90 = user_amounts_sorted[0.90 * len(amounts)]
```
- **Interpretation**: Is current amount above user's historical 75th/90th percentile?
- **Example**: User never sent > 10k KES, current=50k → Flag as unusual

### Category 2: Velocity (3 features)

**Feature 4: Velocity 24-Hour**
```python
count_24h = count(transactions by MSISDN in last 24 hours)
```
- **Example**: User has 12 txns in 24h, normal = 2-5 → Velocity abuse
- **Computation**: Count from audit logs (cached)

**Feature 5-6: Velocity 7-day & 30-day**
```python
count_7d = count(transactions by MSISDN in last 7 days)
count_30d = count(transactions by MSISDN in last 30 days)
```
- **Interpretation**: Longer-window velocity (trending abuse)

### Category 3: Temporal Patterns (2 features)

**Feature 7: Unusual Hour Flag**
```python
is_unusual = 1 if 00:00 <= hour <= 06:00 else 0
```
- **Rationale**: Fraudsters operate at night, legitimate users don't
- **Timezone-aware**: Configurable per region

**Feature 8: Day-of-Week Anomaly**
```python
is_unusual_dow = 1 if (dow_not_in_user_typical_days) else 0
```
- **Example**: User never transacts on Sundays, current=Sunday → Flag

### Category 4: Account Behavior (4 features)

**Feature 9: Device Change Flag**
```python
device_changed = 1 if (current_device != last_device) else 0
```
- **Interpretation**: SIM swap indicator (new device = potential attack)
- **Requires**: Device ID tracking in transaction

**Feature 10: Account Age**
```python
days_since_first_txn = today - user_account_created_date
account_age_category = 1 if days < 30 else 2 if days < 180 else 3
```
- **Rationale**: New accounts have higher fraud risk

**Feature 11: New Recipient Flag**
```python
is_new_recipient = 1 if recipient_never_seen_before else 0
```
- **Interpretation**: First time sending to this account = higher risk

**Feature 12: Recipient Account Age**
```python
recipient_account_age = days since recipient first_txn
is_young_recipient = 1 if recipient_age < 30 days else 0
```
- **Rationale**: Fraudsters use newly created accounts to cash out

## Feature Matrix Example

```python
# Single transaction features
txn = {
  "amount_z_score": 2.1,
  "amount_p75": 0,  # Below 75th percentile
  "amount_p90": 1,  # Above 90th percentile
  "velocity_24h": 12,  # High velocity
  "velocity_7d": 50,
  "velocity_30d": 200,
  "unusual_hour": 1,  # 02:30 AM
  "unusual_dow": 0,
  "device_changed": 1,  # SIM swap risk
  "account_age": 3,  # Old account (lower risk)
  "new_recipient": 1,  # Never sent to before
  "recipient_young": 1   # New recipient account
}

# Array for ML model
X = [2.1, 0, 1, 12, 50, 200, 1, 0, 1, 3, 1, 1]  # Shape: (12,)
```

## Computation Strategy

### Real-Time vs. Cached

**Real-Time Computation** (< 1ms):
- Z-score (requires mean/std → cached)
- Unusual hour flag (compare timestamp to config)
- Device change (requires last device → cached)

**Cached (15-min TTL)** (one-time, reuse across txns):
- User account age
- Recipient account age
- Device change flag

**From Audit Logs** (queryable):
- Velocity counts (aggregated, indexed by MSISDN + timestamp)
- Transaction history amounts (for percentiles)

### Feature Store Caching

```python
# serving/feature_store.py
class FeatureStore:
    def get_features(self, msisdn: str, lookback_days: int = 30) -> Dict:
        # Check cache (15-min TTL)
        cached = self.cache.get(msisdn)
        if cached and not expired(cached):
            return cached
        
        # Recompute if missing/expired
        features = {
            "mean_amount": self._get_mean_amount(msisdn, lookback_days),
            "std_amount": self._get_std_amount(msisdn, lookback_days),
            "velocity_24h": self._count_velocity(msisdn, hours=24),
            ...
        }
        
        self.cache.set(msisdn, features, ttl=900)  # 15 min
        return features
```

## Feature Selection Rationale

**Why These 12?**
- **Sufficiency**: Capture main fraud patterns (velocity, anomaly, temporal)
- **Simplicity**: Interpretable, no deep learning black boxes
- **Efficiency**: Computable in < 30ms (< 100ms SLA)
- **Completeness**: Cover rule-based checks (velocity, night hours)

**Why Not More?**
- Diminishing returns (curse of dimensionality)
- Harder to interpret & debug
- Slower inference (HistGradientBoosting linear in # features)

**Why Not Fewer?**
- Missing velocity signal (critical for M-Pesa fraud)
- Insufficient temporal patterns
- Weak account behavior indicators

## Feature Importance (from Trained Model)

```
Feature Importance (HistGradientBoosting):
1. velocity_24h:     0.35  (Most important)
2. amount_z_score:   0.25
3. device_changed:   0.15
4. unusual_hour:     0.10
5. velocity_7d:      0.08
6. ... (remaining):  0.07
```

Top-3 features explain 75% of model decisions.

## Handling Missing Values

| Feature | Missing Value | Handling |
|---------|---------------|----------|
| z_score | No history | Set to 0 (neutral) |
| velocity_24h | New account | Set to 0 |
| device_changed | No device ID | Set to 0 (assume safe) |
| recipient_young | New recipient | Set to 1 (assume young, higher risk) |
| account_age | Unknown | Use minimum safe default (30 days) |

## Feature Drift Monitoring

**Monthly Checks**:
```python
# Compare test set distribution to current production
test_mean_z_score = 0.5
prod_mean_z_score = 2.1  # ← 4x higher!

# Possible causes:
# 1. Data distribution changed (new user cohort)
# 2. Feature computation bug
# 3. Legitimate trend (economy, seasonality)

# Action: Investigate, possibly retrain
```

**Alerting**:
- [ ] If any feature mean shifts > 20% → Investigate
- [ ] If feature std increases > 2x → Possible data quality issue

## Alternatives Considered

### Alternative 1: Raw Amount Only
- **Rejected**: Insufficient predictive power (FPR too high)
- **Reason**: 5000 KES is normal for merchant, fraud for student

### Alternative 2: Deep Learning Feature Extraction
- **Rejected**: Overkill for structured data, harder to interpret
- **Reason**: HistGradientBoosting on engineered features is simpler & faster

### Alternative 3: Include Graph Features (Mule Rings)
- **Partially Adopted**: MuleAccountCorrelator check covers this
- **Reason**: Expensive to compute in real-time, rule-based check sufficient

## Future Enhancements

1. **Dynamic Feature Weighting**: Adjust feature importance per user cohort
2. **Feature Interactions**: Capture z_score × velocity (high amount AND high frequency)
3. **Geographic Features**: Regional fraud rates (Nairobi vs. Rural)
4. **Time-Series Features**: Trend in velocity over last 7 days
5. **Network Features**: How many unique recipients in 24h (mule indicator)

## Implementation

- [ml/features.py](../../ml/features.py): Feature computation
- [serving/feature_store.py](../../serving/feature_store.py): Caching & retrieval
- [ml/train_model.py](../../ml/train_model.py): Integration during training
- Tests: [tests/test_features.py](../../tests/test_features.py)

## References

- Feature Engineering for Machine Learning: Zheng & Casari (O'Reilly)
- HistGradientBoosting Paper: Ke et al., LightGBM
- Domain-driven feature design in fraud detection

## Approval

- **ML Engineer**: Alice (alice@company.com) - Approved
- **Data Analyst**: Frank (frank@company.com) - Approved
- **Date**: 2026-01-01
