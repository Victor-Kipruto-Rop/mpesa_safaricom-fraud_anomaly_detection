import pytest
from ..checks.velocity_detector import VelocityDetector
from ..checks.sim_swap_correlator import SimSwapCorrelator
from ..checks.night_flagger import NightTransactionFlagger
from ..serving.feature_store import FeatureStore
from ..serving.model_registry import ModelRegistry
from ..checks.ml_scorer import MLFraudScorer
from ..config import FraudConfig
import time


def test_velocity_detector_basic():
    """Test velocity detector with new interface."""
    v = VelocityDetector(short_window_sec=60, long_window_sec=3600, k=1.0)
    msisdn = "m1"
    context = {"feature_snapshot": {"mean_short": 2.0, "std_short": 0.5}}
    # simulate 10 rapid txns
    for _ in range(10):
        r = v.evaluate({"msisdn": msisdn}, context)
    assert r.triggered is True


def test_sim_swap_correlator_basic():
    """Test SIM swap correlator with new interface."""
    s = SimSwapCorrelator(lookback_seconds=3600, amount_threshold=1000.0)
    msisdn = "254700000002"
    now = time.time()
    s.record_swap(msisdn, now - 10)
    out = s.evaluate({"msisdn": msisdn, "amount": 2000}, {})
    assert out.triggered is True


def test_night_flagger_timezone():
    """Test night flagger with new interface."""
    n = NightTransactionFlagger(start_hour=0, end_hour=6)
    from datetime import datetime
    # 02:30 UTC is in night window [00:00, 06:00)
    txn = {"timestamp": "2026-01-01T02:30:00"}
    out = n.evaluate(txn, {})
    assert out.triggered is True


def test_ml_scorer_missing_model():
    """Test ML scorer with no model registered."""
    mr = ModelRegistry()
    fs = FeatureStore()
    ml = MLFraudScorer(mr, fs)
    txn = {"msisdn": "254700000003", "amount": 50, "timestamp": "2026-01-01T03:00:00"}
    res = ml.evaluate(txn, {})
    assert res.triggered is False
