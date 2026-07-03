import pytest

from ..engine import ConsolidatedFraudDetectionEngine
from ..aggregator import FraudScoreAggregator
from ..checks.base import FraudCheck, CheckResult, CheckState


class DummyCheck(FraudCheck):
    """Dummy check for testing."""
    name = "dummy"

    def evaluate(self, txn, context):
        # Return a low score
        return CheckResult(name=self.name, score=0.0, triggered=False, reason="dummy", weight=1.0, state=CheckState.OK)


def test_engine_scores_transaction():
    """Test that engine can score a transaction."""
    checks = [DummyCheck()]
    agg = FraudScoreAggregator()
    engine = ConsolidatedFraudDetectionEngine({}, {"mobile_money": checks}, agg)
    
    txn = {"txn_id": "t1", "msisdn": "254700000000", "amount": 10, "timestamp": "2026-01-01T03:00:00"}
    result = engine.score(txn)
    
    assert hasattr(result, "decision")
    assert hasattr(result, "score")
    assert result.decision.value in ("ALLOW", "REVIEW", "BLOCK")
    assert 0.0 <= result.score <= 1.0


def test_engine_creates_audit_log():
    """Test that engine logs transactions to audit log."""
    checks = [DummyCheck()]
    agg = FraudScoreAggregator()
    engine = ConsolidatedFraudDetectionEngine({}, {"mobile_money": checks}, agg)
    
    txn = {"txn_id": "t2", "msisdn": "254700000001", "amount": 50, "timestamp": "2026-01-01T03:00:00"}
    result = engine.score(txn)
    
    assert len(engine.audit_log) > 0
    assert engine.audit_log[-1]["txn"] == txn
