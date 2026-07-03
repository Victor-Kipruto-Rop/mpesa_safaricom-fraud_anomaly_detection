# ADR-0003: Circuit Breaker Pattern for Resilience

**Date**: 2026-01-01  
**Status**: Accepted  
**Context**: Fraud detection must be resilient to downstream failures (DB latency, model loading issues, check timeouts)  
**Decision**: Implement Circuit Breaker pattern to gracefully degrade service rather than cascading failures.

## Problem

Fraud detection depends on multiple components:
- ML model inference (network, disk, memory)
- Feature store queries (database, cache)
- Individual checks (VelocityDetector, MLScorer, etc.)
- Configuration loading

**Failure Modes**:
1. **Model Load Failure**: joblib.load() hangs → API times out → Entire service down
2. **Check Timeout**: VelocityDetector takes > 5s → All transactions block → Cascading failures
3. **DB Unavailable**: Can't fetch user history → All features fail → System paralyzed

Without protection, single component failure brings down entire fraud detection, impacting:
- User transactions stuck
- Real fraud slips through (can't block)
- Revenue loss & customer complaints

## Solution

Implement Circuit Breaker with 3 states:

```python
class CircuitBreaker:
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, refuse calls
    HALF_OPEN = "half_open"  # Testing recovery
    
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 60):
        self.state = self.CLOSED
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout  # seconds
    
    def call(self, func, *args, **kwargs):
        if self.state == self.OPEN:
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = self.HALF_OPEN
            else:
                raise CircuitBreakerOpen()
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_failure(self):
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = self.OPEN
            self.last_failure_time = time.time()
    
    def _on_success(self):
        self.failure_count = 0
        self.state = self.CLOSED
```

**State Transitions**:

```
        ┌──────────────┐
        │   CLOSED     │ ← Normal operation
        │ (call fn)    │   All calls succeed
        └──────┬───────┘
               │ 5 consecutive failures
               ↓
        ┌──────────────┐
        │     OPEN     │ ← Failing
        │ (refuse)     │   All calls rejected
        └──────┬───────┘   (Fail-safe)
               │ 60 seconds elapsed
               ↓
        ┌──────────────┐
        │ HALF_OPEN    │ ← Testing recovery
        │ (allow 1%)   │   Try limited calls
        └──────┬───────┘
               ├─ Success → CLOSED
               └─ Failure → OPEN (restart timer)
```

**Integration with Fraud Detection**:

```python
# In engine.py
class ConsolidatedFraudDetectionEngine:
    def __init__(self):
        self.model_breaker = CircuitBreaker(failure_threshold=5)
        self.velocity_breaker = CircuitBreaker(failure_threshold=10)
        self.feature_store_breaker = CircuitBreaker(failure_threshold=3)
    
    def score_transaction(self, txn):
        try:
            features = self.feature_store_breaker.call(
                self.compute_features, txn
            )
        except CircuitBreakerOpen:
            # Feature store down → Use cached/default features
            features = self.get_cached_features(txn)
        
        try:
            ml_score = self.model_breaker.call(
                self.ml_scorer.score, features
            )
        except CircuitBreakerOpen:
            # ML model down → Use rule-based score only
            ml_score = 0  # Neutral, rely on checks
        
        # Continue with other checks (may be slower, but system up)
        return self.aggregate_scores(...)
```

**Advantages**:
- ✅ Fails gracefully (ACCEPT or degrade to rules-only, not BLOCK all)
- ✅ Prevents cascading failures (stops hammering broken component)
- ✅ Auto-recovery (HALF_OPEN state tests if component recovered)
- ✅ Simple to implement & test

**Trade-offs**:
- ❌ May allow false negatives during component failure (fraud slips through)
  - Mitigation: Log all bypass decisions for async review
- ❌ Configuration tuning needed (failure thresholds vary by component)
  - Mitigation: Start conservative, monitor, adjust

## Failure Scenarios Handled

### Scenario 1: ML Model Crash
```
State: CLOSED
ML scorer fails 5 times in a row
State: OPEN (circuit trips)
Incoming transactions:
- Velocity check: PASS
- SIM swap: PASS
- Night flag: PASS
- ML scorer: SKIPPED (breaker open)
Decision: Based on rule-only (conservative)
Status: Service up, fraud detection degraded but available
```

### Scenario 2: Feature Store (DB) Slow
```
State: CLOSED
Feature store queries taking > 5s each
5 consecutive timeouts
State: OPEN
New transactions:
- Use cached features from 15 min ago
- Less accurate, but deterministic
Decision: Risk score may be slightly off, but ~available
```

### Scenario 3: Recovery
```
State: OPEN (60s passed)
State: HALF_OPEN (allow limited calls)
Component recovers → 100% success rate
State: CLOSED (back to normal)
```

## Configuration

```python
# config.py
class FraudConfig:
    circuit_breaker_failure_threshold: int = 5  # # failures before trip
    circuit_breaker_reset_timeout: int = 60     # seconds before retry
    circuit_breaker_failure_threshold_model: int = 3  # stricter for model
```

**Per-Component Thresholds**:
- Model: 3 failures (strict, ML is critical)
- Velocity check: 10 failures (lenient, lightweight)
- Feature store: 5 failures (moderate)

## Alternatives Considered

### Alternative 1: Retry with Exponential Backoff
- **Rejected**: Only delays failure, doesn't prevent cascading
- **Issue**: If component is down, retries waste time & resources

### Alternative 2: Timeout Only
- **Rejected**: Timeout is reactive, not preventive
- **Issue**: Still hammers failing component, slow response

### Alternative 3: Fallback to Baseline Model
- **Rejected**: Requires maintaining multiple models
- **Complexity**: When to switch, testing effort

## Monitoring & Alerting

**Metrics**:
```
circuit_breaker_state{component="model"}            # 0=CLOSED, 1=OPEN, 2=HALF_OPEN
circuit_breaker_failures_total{component="model"}   # Counter
circuit_breaker_trips{component="model"}            # How many times tripped
```

**Alerts**:
- [ ] If breaker OPEN for > 5 min → Page on-call
- [ ] If HALF_OPEN for > 10 min (slow recovery) → Investigate
- [ ] If > 10 trips in 24h → Review component reliability

## Testing

- [tests/test_fraud_components.py](../../tests/test_fraud_components.py): CircuitBreaker state transitions
- Unit test: Verify CLOSED → OPEN → HALF_OPEN → CLOSED cycle
- Integration test: Simulate ML model failure, verify system stays up

## Implementation

- [circuit_breaker.py](../../circuit_breaker.py): Core implementation
- [engine.py](../../engine.py): Integration with fraud detection pipeline
- Config integration: [config.py](../../config.py)

## Future Enhancements

1. **Per-Transaction Circuit Breaker**: Different thresholds per user tier
2. **Adaptive Thresholds**: Auto-tune based on component health trends
3. **Circuit Breaker Dashboard**: Real-time breaker state visualization
4. **Fallback Strategies**: Pluggable fallbacks (cache, ML-only, rules-only, ACCEPT-all)

## References

- Martin Fowler: Circuit Breaker Pattern
- Netflix Hystrix: Original implementation (Java)
- AWS DynamoDB Exponential Backoff & Jitter

## Approval

- **Platform Engineer**: Bob (bob@company.com) - Approved
- **SRE Lead**: Eve (eve@company.com) - Approved
- **Date**: 2026-01-01
