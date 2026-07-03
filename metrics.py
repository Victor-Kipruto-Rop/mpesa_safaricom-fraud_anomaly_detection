from prometheus_client import Counter, Gauge, Histogram

# metrics for observability
SCORING_LATENCY = Histogram(
    "fraud_scoring_latency_seconds",
    "Latency for fraud scoring",
    buckets=(0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0),
)

CHECK_TRIGGER = Counter("fraud_check_trigger_total", "Per-check trigger count", ["check"])

DEPENDENCY_FAILURE = Counter(
    "fraud_dependency_failure_total", "Dependency failure (redis/model/config) occurrences", ["dependency"]
)

SCORE_DISTRIBUTION = Histogram("fraud_score_distribution", "Distribution of final fraud scores", buckets=(0, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0))

CIRCUIT_BREAKER_TRIPPED_TOTAL = Counter(
    "fraud_circuit_breaker_tripped_total",
    "Number of times the fraud engine circuit breaker opened",
)

BATCH_RECONCILIATION_TOTAL = Counter(
    "fraud_batch_reconciliation_total",
    "Count of batch reconciliation operations performed",
)

BATCH_RECONCILIATION_MISSING_TOTAL = Counter(
    "fraud_batch_reconciliation_missing_total",
    "Count of missing audit records found during batch reconciliation",
)
