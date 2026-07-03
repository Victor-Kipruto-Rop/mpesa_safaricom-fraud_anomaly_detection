"""Simple drift monitoring utilities (PSI) to compare two distributions.

This module provides functions to compute PSI and write a small report.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def psi(expected: np.ndarray, actual: np.ndarray, buckets: int = 10) -> float:
    """Population Stability Index between two arrays."""
    def _to_bins(arr, buckets):
        return np.histogram(arr, bins=buckets)[0].astype(float)

    exp_bins = _to_bins(expected, buckets)
    act_bins = _to_bins(actual, buckets)
    # avoid zeros
    exp_perc = exp_bins / (exp_bins.sum() + 1e-9)
    act_perc = act_bins / (act_bins.sum() + 1e-9)
    psi_vals = (exp_perc - act_perc) * np.log((exp_perc + 1e-9) / (act_perc + 1e-9))
    return float(np.sum(psi_vals))


def compare_feature_distributions(train_feats: pd.DataFrame, recent_feats: pd.DataFrame, feature_list=None):
    if feature_list is None:
        feature_list = train_feats.columns.intersection(recent_feats.columns).tolist()
    report = {}
    for f in feature_list:
        try:
            report[f] = psi(train_feats[f].values, recent_feats[f].values)
        except Exception:
            report[f] = None
    return report
