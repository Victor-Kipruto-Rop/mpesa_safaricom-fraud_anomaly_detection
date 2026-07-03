import pytest
from fraud_detection_unified.engine import ConsolidatedFraudDetectionEngine


def test_engine_handles_both_domains():
    engine = ConsolidatedFraudDetectionEngine()
    # mobile money txn
    mm = {
        "txn_id": "MM1",
        "amount": 10000,
        "velocity_60s": 1,
        "sim_swap_days": -1,
        "timestamp": "2025-01-08T10:00:00",
        "institution": "MPESA",
    }
    bnk = {
        "txn_id": "B1",
        "account_id": "ACC1",
        "amount": 100000,
        "txn_type": "Transfer",
        "is_pep": False,
        "timestamp": "2025-01-08T10:00:00",
        "institution": "BANK",
    }
    a1 = engine.score_mobile_money_transaction(mm)
    a2 = engine.score_banking_transaction(bnk)
    assert a1 is not None and a2 is not None
