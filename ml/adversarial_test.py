"""Generate adversarial-like transactions to test evasion resistance.

Creates small perturbations around thresholds and evaluates a provided inference callable.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Callable, Dict, Any


def generate_velocity_evasion(msisdn: str, base_ts, n=9, interval_seconds=7, amount=10.0):
    rows = []
    for i in range(n):
        ts = base_ts + pd.Timedelta(seconds=i * interval_seconds)
        rows.append({
            'txn_id': f'adversary-{i}',
            'msisdn': msisdn,
            'amount': amount,
            'currency': 'KES',
            'timestamp': ts.isoformat(),
            'label': 0,
        })
    return pd.DataFrame(rows)


def run_adversarial_suite(infer: Callable[[Dict[str, Any]], Dict[str, Any]], samples: pd.DataFrame, features_fn: Callable[[Dict[str, Any]], Dict[str, Any]]):
    results = []
    for _, r in samples.iterrows():
        fv = features_fn(r)['vector']
        res = infer(fv)
        results.append({'txn_id': r['txn_id'], 'score': res.get('score'), 'model_version': res.get('model_version')})
    return pd.DataFrame(results)
