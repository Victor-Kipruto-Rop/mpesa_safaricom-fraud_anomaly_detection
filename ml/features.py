"""Feature engineering shared by training and serving."""
from __future__ import annotations
from typing import Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime


def hour_of_day_feature(ts: str) -> int:
    try:
        d = datetime.fromisoformat(ts)
        return d.hour
    except Exception:
        return 12


def compute_features_for_df(df: pd.DataFrame) -> pd.DataFrame:
    """Compute features for each txn in dataframe and return feature dataframe."""
    df = df.copy()
    df["hour"] = df["timestamp"].apply(hour_of_day_feature)
    # cyclic encode hour
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)

    # amount log
    df["log_amount"] = np.log1p(df["amount"].astype(float))

    # simplistic customer stats: avg amount per msisdn
    avg = df.groupby("msisdn")["amount"].transform("mean")
    df["amount_dev"] = df["amount"] / (avg + 1e-9)

    # time since last txn per msisdn (sorted by timestamp)
    df["ts_dt"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(["msisdn", "ts_dt"]).reset_index(drop=True)
    df["prev_ts"] = df.groupby("msisdn")["ts_dt"].shift(1)
    df["secs_since_prev"] = (df["ts_dt"] - df["prev_ts"]).dt.total_seconds().fillna(1e6)

    # rolling counts: last 1h, 24h -- compute per-group to avoid reindex issues
    df["count_1h"] = 0.0
    df["count_24h"] = 0.0

    # Behavioral baselining windows (7d, 30d, 90d)
    for w_label, window in [("7d", "7d"), ("30d", "30d"), ("90d", "90d")]:
        df[f"amt_mean_{w_label}"] = 0.0
        df[f"amt_std_{w_label}"] = 0.0
        df[f"cnt_{w_label}"] = 0.0
        df[f"sum_amt_{w_label}"] = 0.0

    def _compute_group(g):
        g = g.set_index("ts_dt")
        g = g.sort_index()
        g["count_1h"] = g["txn_id"].rolling("1h").count()
        g["count_24h"] = g["txn_id"].rolling("24h").count()
        # compute rolling stats for windows
        for w_label, window in [("7d", "7d"), ("30d", "30d"), ("90d", "90d")]:
            amt_mean = g["amount"].rolling(window).mean()
            amt_std = g["amount"].rolling(window).std()
            cnt = g["txn_id"].rolling(window).count()
            sum_amt = g["amount"].rolling(window).sum()
            g[f"amt_mean_{w_label}"] = amt_mean
            g[f"amt_std_{w_label}"] = amt_std
            g[f"cnt_{w_label}"] = cnt
            g[f"sum_amt_{w_label}"] = sum_amt
        return g

    # apply per-group and concatenate to ensure group key column is preserved
    parts = []
    for _, g in df.groupby("msisdn"):
        g2 = g.copy()
        g2 = _compute_group(g2)
        g2 = g2.reset_index()
        parts.append(g2)
    if parts:
        df = pd.concat(parts, ignore_index=True)
    else:
        # empty input
        df = df.reset_index(drop=True)

    # RFM-style features + behavioral baselines
    rfm_cols = ["secs_since_prev"]
    baseline_cols = ["amt_mean_7d", "amt_std_7d", "cnt_7d", "sum_amt_7d", "amt_mean_30d", "amt_std_30d", "cnt_30d", "sum_amt_30d", "amt_mean_90d", "amt_std_90d", "cnt_90d", "sum_amt_90d"]
    feature_cols = ["log_amount", "hour_sin", "hour_cos", "amount_dev"] + rfm_cols + ["count_1h", "count_24h"] + baseline_cols
    features = df[feature_cols].fillna(0)
    # return df with feature vector column
    df["feature_vector"] = features.values.tolist()
    return df


def features_for_transaction(record: Dict[str, Any], feature_store_snapshot: Dict[str, Any] = None) -> Dict[str, Any]:
    """Compute features for a single transaction at inference time.

    `feature_store_snapshot` can supply customer historical aggregates.
    Returns feature vector with all 19 expected by the model.
    """
    fv = {}
    fv["log_amount"] = float(np.log1p(record.get("amount", 0.0)))
    hour = hour_of_day_feature(record.get("timestamp", ""))
    fv["hour_sin"] = float(np.sin(2 * np.pi * hour / 24))
    fv["hour_cos"] = float(np.cos(2 * np.pi * hour / 24))
    avg = None
    if feature_store_snapshot:
        avg = feature_store_snapshot.get("avg_amount")
    if not avg:
        avg = record.get("amount", 0.0)
    fv["amount_dev"] = float(record.get("amount", 0.0)) / (avg + 1e-9)
    fv["secs_since_prev"] = float(feature_store_snapshot.get("secs_since_prev", 1e6) if feature_store_snapshot else 1e6)
    fv["count_1h"] = float(feature_store_snapshot.get("count_1h", 0) if feature_store_snapshot else 0)
    fv["count_24h"] = float(feature_store_snapshot.get("count_24h", 0) if feature_store_snapshot else 0)
    
    # behavioral baselines (7d, 30d, 90d) - default to 0 if not in snapshot
    for w in ["7d", "30d", "90d"]:
        fv[f"amt_mean_{w}"] = float(feature_store_snapshot.get(f"amt_mean_{w}", 0) if feature_store_snapshot else 0)
        fv[f"amt_std_{w}"] = float(feature_store_snapshot.get(f"amt_std_{w}", 0) if feature_store_snapshot else 0)
        fv[f"cnt_{w}"] = float(feature_store_snapshot.get(f"cnt_{w}", 0) if feature_store_snapshot else 0)
        fv[f"sum_amt_{w}"] = float(feature_store_snapshot.get(f"sum_amt_{w}", 0) if feature_store_snapshot else 0)
    
    feature_order = ["log_amount", "hour_sin", "hour_cos", "amount_dev", "secs_since_prev", "count_1h", "count_24h",
                     "amt_mean_7d", "amt_std_7d", "cnt_7d", "sum_amt_7d",
                     "amt_mean_30d", "amt_std_30d", "cnt_30d", "sum_amt_30d",
                     "amt_mean_90d", "amt_std_90d", "cnt_90d", "sum_amt_90d"]
    return {"vector": [fv[c] for c in feature_order], "raw": fv}
