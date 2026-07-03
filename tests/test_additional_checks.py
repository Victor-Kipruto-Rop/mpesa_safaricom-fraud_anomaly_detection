import time
import json
from ..checks.velocity_detector import VelocityDetector
from ..checks.sim_swap_correlator import SimSwapCorrelator
from ..checks.night_flagger import NightTransactionFlagger
from ..batch_reconcile import reconcile
from ..aggregator import FraudScoreAggregator
from ..serving.model_registry import ModelRegistry
from ..serving.feature_store import FeatureStore
from ..checks.ml_scorer import MLFraudScorer
from ..checks.mule_correlator import MuleAccountCorrelator
from ..engine import ConsolidatedFraudDetectionEngine


def test_velocity_detector_triggers():
    v = VelocityDetector(short_window_sec=60, long_window_sec=3600, k=1.0)
    msisdn = "m1"
    now = time.time()
    # seed store with history: mean_short=2, std_short=1 in context
    context = {"feature_snapshot": {"mean_short": 2.0, "std_short": 0.5}}
    # simulate 10 rapid txns
    for _ in range(10):
        r = v.evaluate({"msisdn": msisdn}, context)
    assert r.triggered is True


def test_sim_swap_correlator_behaviour():
    s = SimSwapCorrelator(lookback_seconds=3600, amount_threshold=1000.0)
    msisdn = "254700000002"
    now = time.time()
    s.record_swap(msisdn, now - 10)
    out = s.evaluate({"msisdn": msisdn, "amount": 2000}, {})
    assert out.triggered is True


def test_night_flagger():
    n = NightTransactionFlagger(start_hour=0, end_hour=6)
    txn = {"timestamp": "2026-01-01T02:30:00"}
    out = n.evaluate(txn, {})
    assert out.triggered is True


def test_batch_reconcile_counts_divergence():
    # build a minimal engine that will flip one decision
    registry = ModelRegistry()
    from sklearn.dummy import DummyClassifier
    import joblib
    # train a tiny classifier that predicts high fraud probability
    X = [[0.0], [1.0]]
    y = [0, 1]
    clf = DummyClassifier(strategy="constant", constant=1)
    clf.fit(X, y)
    joblib_path = "/tmp/fake2.joblib"
    joblib.dump(clf, joblib_path)
    lm = registry.load_from_paths("v1", joblib_path, None)
    registry.register_champion(lm)
    fs = FeatureStore()
    fs.put_snapshot("254700000003", {"avg_amount": 1.0})
    checks = [MLFraudScorer(registry, fs), MuleAccountCorrelator()]
    agg = FraudScoreAggregator()
    engine = ConsolidatedFraudDetectionEngine({}, {"mobile_money": checks}, agg)

    # original audit had an ALLOW
    txn = {"txn_id": "x1", "msisdn": "254700000003", "amount": 5000, "timestamp": "2026-01-01T03:00:00"}
    audit_lines = [json.dumps({"txn": txn, "decision": "ALLOW"})]
    res = reconcile(audit_lines, engine)
    assert res["total"] == 1
    assert res["divergences"] >= 1
