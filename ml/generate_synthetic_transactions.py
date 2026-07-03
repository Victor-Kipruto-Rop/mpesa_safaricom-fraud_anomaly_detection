"""Generate synthetic mobile money transactions for training/testing.

Produces a Parquet file with labeled transactions.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import uuid
import os


def generate(n=50000, out_path="./mpesa_safaricom/fraud_anomaly_detection/ml/synthetic_transactions.parquet"):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    rng = np.random.default_rng(42)

    rows = []
    base_time = datetime.utcnow()
    for i in range(n):
        msisdn = f"+2547{rng.integers(10000000,99999999):08d}"
        amount = float(np.exp(rng.normal(8.0, 1.2)))  # log-normal-like
        # time distribution: daytime more common
        hour = int(abs(int(rng.normal(12, 6)))) % 24
        ts = (base_time - timedelta(seconds=int(rng.integers(0, 86400*30)))) + timedelta(hours=hour%24)

        # default labels 0 (normal)
        label = 0

        # inject fraud types
        # velocity bursts: small amount but many in short time
        if rng.random() < 0.01:
            # create a velocity burst cluster
            label = 1
            amount = float(np.exp(rng.normal(5.0, 0.5)))

        # sim-swap + high value
        sim_swap = False
        if rng.random() < 0.005:
            sim_swap = True
            if rng.random() < 0.5:
                label = 1
                amount = amount * 10

        # night fraud
        if 0 <= hour <= 4 and rng.random() < 0.02:
            label = 1

        # ML-only subtle fraud
        if rng.random() < 0.005:
            label = 1

        rows.append({
            "txn_id": str(uuid.uuid4()),
            "msisdn": msisdn,
            "amount": round(amount, 2),
            "currency": "KES",
            "timestamp": ts.isoformat(),
            "sim_swap": sim_swap,
            "label": int(label),
        })

    df = pd.DataFrame(rows)
    df.to_parquet(out_path, index=False)
    print(f"Wrote {len(df)} rows to {out_path}")


if __name__ == "__main__":
    generate()
