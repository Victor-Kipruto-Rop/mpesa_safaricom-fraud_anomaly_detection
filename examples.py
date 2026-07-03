"""Examples and small test harness for the fraud engine."""
from .engine import MobileMoneyFraudEngine
from datetime import datetime, timedelta


def run_example():
    engine = MobileMoneyFraudEngine()

    now = datetime.utcnow()
    base_txn = {
        "transaction_id": "txn-1",
        "account_id": "acct-123",
        "msisdn": "+254700000000",
        "sim_serial": "sim-111",
        "amount": 15000.0,
        "timestamp": now.isoformat(),
    }

    history = []
    # create 10 recent small txns to trigger velocity
    for i in range(9):
        history.append({
            "transaction_id": f"h{i}",
            "account_id": "acct-123",
            "sim_serial": "sim-111",
            "amount": 10.0,
            "timestamp": (now - timedelta(seconds=5 * i)).isoformat(),
        })

    alert = engine.score_mobile_money_transaction(base_txn, history=history)
    print(alert)


if __name__ == "__main__":
    run_example()
