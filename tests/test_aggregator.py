from ..aggregator import FraudScoreAggregator, Decision
from ..checks.base import CheckResult, CheckState


def test_aggregator_combines():
    """Test aggregator combines check results into a fraud score decision."""
    agg = FraudScoreAggregator({})
    results = [
        CheckResult(name="ml", score=0.8, triggered=True, reason="ml", weight=1.0, state=CheckState.TRIGGERED),
        CheckResult(name="velocity", score=0.5, triggered=True, reason="vel", weight=0.5, state=CheckState.TRIGGERED),
        CheckResult(name="sim_swap", score=0.0, triggered=False, reason="no", weight=0.3, state=CheckState.OK),
        CheckResult(name="night", score=0.2, triggered=True, reason="night", weight=0.3, state=CheckState.TRIGGERED),
    ]
    out = agg.aggregate(results)
    assert out.decision in (Decision.ALLOW, Decision.REVIEW, Decision.BLOCK)
    assert hasattr(out, "score")
    assert 0.0 <= out.score <= 1.0
