import json

from ingestion.webhook_receiver import create_app
from ingestion.metrics import get_metrics_collector


def test_c2b_confirmation_endpoint_and_metrics_present():
    app = create_app()
    app.testing = True
    client = app.test_client()

    metrics = get_metrics_collector()

    payload = {
        "TransID": "T_TEST_1",
        "TransAmount": "100",
        "MSISDN": "254712345678",
        "TransTime": "20260101010101",
    }

    resp = client.post("/webhook/c2b/confirmation", json=payload)
    assert resp.status_code == 200

    # Ensure metrics collector API is available
    assert hasattr(metrics, "record_webhook_request")
    assert hasattr(metrics, "record_message_processed")
