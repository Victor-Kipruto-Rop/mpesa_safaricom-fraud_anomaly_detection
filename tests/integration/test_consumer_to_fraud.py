from app.services.fraud_detection_service import StreamingFraudDetectionService


def test_process_transaction_returns_alert_or_none():
    svc = StreamingFraudDetectionService()

    txn = {
        "transaction_id": "TXN_TEST",
        "amount": 1000000,
        "institution": "MPESA",
        "txn_type": "C2B",
        "timestamp": "2026-07-03T12:00:00",
    }

    result = svc.process_transaction(txn)

    # Ensure call is safe and returns either None or an alert dict
    assert result is None or isinstance(result, dict)
    if isinstance(result, dict):
        assert "alert_id" in result
        assert "risk_score" in result
