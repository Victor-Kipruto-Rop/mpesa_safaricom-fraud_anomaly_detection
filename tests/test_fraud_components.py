import tempfile
import pytest
import joblib
import os
import numpy as np

from ..serving.model_registry import ModelRegistry
from ..serving.feature_store import FeatureStore
from ..checks.ml_scorer import MLFraudScorer
from ..aggregator import FraudScoreAggregator
from ..checks.mule_correlator import MuleAccountCorrelator
from ..circuit_breaker import CircuitBreaker
from ..checks.base import CheckResult, CheckState


class FakeCalibrator:
    def __init__(self, score: float):
        self._score = score

    def predict_proba(self, X):
        n = len(X)
        # return [[1-score, score], ...]
        return np.vstack([np.array([1 - self._score, self._score]) for _ in range(n)])


def test_champion_challenger_shadow(tmp_path):
    # create two fake calibrated models and dump
    champ = FakeCalibrator(0.9)
    chal = FakeCalibrator(0.2)
    champ_path = tmp_path / "champ.joblib"
    chal_path = tmp_path / "chal.joblib"
    joblib.dump(champ, str(champ_path))
    joblib.dump(chal, str(chal_path))

    registry = ModelRegistry()
    champ_loaded = registry.load_from_paths("v1", str(champ_path), None)
    chal_loaded = registry.load_from_paths("v2", str(chal_path), None)
    registry.register_champion(champ_loaded)
    registry.register_challenger(chal_loaded)

    fs = FeatureStore()
    fs.put_snapshot("254700000001", {"avg_amount": 10.0, "last_amount": 5.0})

    scorer = MLFraudScorer(registry, fs)
    txn = {"txn_id": "t1", "msisdn": "254700000001", "amount": 5.0, "timestamp": "2026-01-01T00:00:00"}
    ctx = {}
    res = scorer.evaluate(txn, ctx)
    assert res.score == pytest.approx(0.9, rel=1e-3)
    # shadow scores recorded
    assert "__shadow_scores__" in ctx
    assert ctx["__shadow_scores__"]["ml_scorer"]["champion"] == pytest.approx(0.9)
    assert ctx["__shadow_scores__"]["ml_scorer"]["challenger"] == pytest.approx(0.2)


def test_aggregator_interaction():
    agg = FraudScoreAggregator(config={"interactions": {("a", "b"): 0.5}, "thresholds": {"block": 0.9, "review": 0.3}})
    r1 = CheckResult(name="a", score=0.2, triggered=True, reason="a", weight=0.5, state=CheckState.TRIGGERED)
    r2 = CheckResult(name="b", score=0.25, triggered=True, reason="b", weight=0.5, state=CheckState.TRIGGERED)
    out = agg.aggregate([r1, r2])
    # base score = 0.2*0.5 + 0.25*0.5 = 0.225; interaction adds 0.5 -> 0.725
    assert out.score > 0.5
    assert out.decision.name in ("REVIEW", "BLOCK")


def test_mule_correlator_flags_and_not_flags():
    m = MuleAccountCorrelator(window_seconds=3600, sender_threshold=3)
    # create three senders that are interconnected (legitimate)
    m.add_historical_connection("s1", "s2")
    m.add_historical_connection("s2", "s3")
    # simulate txns from s1,s2,s3 to same receiver
    receiver = "acct1"
    t = {"msisdn": "s1", "receiver": receiver, "amount": 10}
    m.evaluate(t, {})
    m.evaluate({"msisdn": "s2", "receiver": receiver, "amount": 8}, {})
    out = m.evaluate({"msisdn": "s3", "receiver": receiver, "amount": 5}, {})
    # since senders are historically connected, should not trigger
    assert out.triggered is False

    # now new correlator with unconnected senders
    m2 = MuleAccountCorrelator(window_seconds=3600, sender_threshold=3)
    m2.evaluate({"msisdn": "a1", "receiver": receiver, "amount": 1}, {})
    m2.evaluate({"msisdn": "a2", "receiver": receiver, "amount": 1}, {})
    out2 = m2.evaluate({"msisdn": "a3", "receiver": receiver, "amount": 1}, {})
    assert out2.triggered is True


def test_circuit_breaker_trip_and_recover():
    cb = CircuitBreaker(fail_max=2, reset_timeout=1.0)

    def bad():
        raise ValueError("boom")

    try:
        cb.call(bad)
    except Exception:
        pass
    try:
        cb.call(bad)
    except Exception:
        pass

    # should be open now
    assert cb.state.name == "OPEN"

    import time

    time.sleep(1.1)

    # next call should go through half-open and then raise
    try:
        cb.call(lambda: 1)
    except Exception:
        pass
    # ensure state closed after successful call
    assert cb.state.name in ("CLOSED", "HALF_OPEN")
