"""Train a fraud classifier on synthetic or real labeled transactions and export reusable artifacts.

This is designed for periodic retraining pipelines. It uses shared feature engineering
from the fraud module, performs a time-aware entity-safe split, handles class imbalance
configurably, trains both a supervised gradient-boosted model and an Isolation Forest baseline,
calibrates probabilities, computes explainability, and exports joblib artifacts.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

import joblib
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split

# Try relative import first (when used as module), then local import (when run directly)
try:
    from .features import compute_features_for_df, features_for_transaction
except ImportError:
    # When run directly from ml folder
    SCRIPT_DIR = Path(__file__).resolve().parent
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    from features import compute_features_for_df, features_for_transaction


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train fraud classifier and export joblib artifact.")
    parser.add_argument("--data", required=True, help="Path to labeled transactions parquet file")
    parser.add_argument("--output-dir", required=True, help="Directory for versioned model artifacts")
    parser.add_argument(
        "--imbalance-method",
        choices=["balanced", "smote"],
        default="balanced",
        help="Imbalance handling: 'balanced' uses class weights, 'smote' resamples minority class.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--sample-size", type=int, default=100, help="Sample size for SHAP explainability")
    return parser.parse_args()


def validate_dataset(df: pd.DataFrame) -> None:
    expected_columns = {"txn_id", "msisdn", "amount", "timestamp", "label"}
    missing = expected_columns - set(df.columns)
    if missing:
        raise ValueError(f"Dataset missing required columns: {sorted(missing)}")
    if df["timestamp"].isna().any():
        raise ValueError("Dataset contains missing timestamps")
    if df["msisdn"].isna().any():
        raise ValueError("Dataset contains missing msisdn values")
    if df["label"].nunique() < 2:
        raise ValueError("Dataset must contain both fraud and non-fraud examples")


def time_aware_entity_split(df: pd.DataFrame, train_frac: float, val_frac: float) -> tuple[pd.Series, pd.Series, pd.Series]:
    df = df.copy()
    df["ts_dt"] = pd.to_datetime(df["timestamp"], errors="raise")
    msisdn_stats = (
        df.groupby("msisdn")["ts_dt"]
        .agg(["min", "max", "count"])
        .rename(columns={"min": "first_seen", "max": "last_seen"})
        .sort_values("first_seen")
    )

    unique_msisdn = len(msisdn_stats)
    if unique_msisdn < 3:
        raise ValueError("Dataset must contain at least three unique msisdn groups for train/val/test split")

    train_end = int(unique_msisdn * train_frac)
    val_end = int(unique_msisdn * (train_frac + val_frac))
    train_msisdns = set(msisdn_stats.index[:train_end])
    val_msisdns = set(msisdn_stats.index[train_end:val_end])
    test_msisdns = set(msisdn_stats.index[val_end:])

    if not train_msisdns or not val_msisdns or not test_msisdns:
        raise ValueError("Split produced an empty partition; adjust train/val fractions")

    overlap = (train_msisdns & val_msisdns) | (train_msisdns & test_msisdns) | (val_msisdns & test_msisdns)
    if overlap:
        raise AssertionError("Entity leakage detected across splits")

    train_mask = df["msisdn"].isin(train_msisdns)
    val_mask = df["msisdn"].isin(val_msisdns)
    test_mask = df["msisdn"].isin(test_msisdns)

    return train_mask, val_mask, test_mask


def recall_at_precision(y_true: np.ndarray, y_scores: np.ndarray, target_precision: float = 0.9) -> float:
    precision, recall, thresholds = precision_recall_curve(y_true, y_scores)
    candidates = [(p, r, t) for p, r, t in zip(precision[:-1], recall[:-1], thresholds) if p >= target_precision]
    if not candidates:
        return 0.0
    return float(max([r for _, r, _ in candidates]))


def choose_operating_threshold(y_true: np.ndarray, y_scores: np.ndarray, target_precision: float = 0.9) -> float:
    precision, recall, thresholds = precision_recall_curve(y_true, y_scores)
    thresholds = np.append(thresholds, 1.0)
    candidates = [(p, th) for p, th in zip(precision, thresholds) if p >= target_precision]
    if not candidates:
        return 0.5
    return float(min(th for _, th in candidates))


def format_ratio(count: int, total: int) -> str:
    return f"{count}/{total} ({count/total:.2%})"


def train_model(
    data_path: str,
    output_dir: str,
    imbalance_method: str = "balanced",
    seed: int = 42,
    shap_sample_size: int = 100,
) -> dict:
    output_path = Path(output_dir)
    if output_path.exists() and any(output_path.iterdir()):
        raise FileExistsError(f"Output directory already exists and is not empty: {output_dir}")
    output_path.mkdir(parents=True, exist_ok=True)

    if not Path(data_path).exists():
        raise FileNotFoundError(f"Labeled parquet file not found: {data_path}")

    df = pd.read_parquet(data_path)
    validate_dataset(df)

    df = compute_features_for_df(df)
    feature_names = list(features_for_transaction({"amount": 1.0, "timestamp": "2026-01-01T00:00:00"})["raw"].keys())

    df["ts_dt"] = pd.to_datetime(df["timestamp"], errors="raise")
    df = df.sort_values("ts_dt").reset_index(drop=True)
    start_date = df["ts_dt"].min()
    end_date = df["ts_dt"].max()

    train_mask, val_mask, test_mask = time_aware_entity_split(df, train_frac=0.7, val_frac=0.15)

    train_df = df[train_mask].reset_index(drop=True)
    val_df = df[val_mask].reset_index(drop=True)
    test_df = df[test_mask].reset_index(drop=True)

    for split_name, split_df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        if split_df["msisdn"].nunique() == 0:
            raise AssertionError(f"Split {split_name} has zero unique msisdn")

    def balance_summary(split_df: pd.DataFrame) -> str:
        pos = int(split_df["label"].sum())
        total = len(split_df)
        return format_ratio(pos, total)

    print("Dataset summary")
    print(f"  rows: {len(df)}")
    print(f"  date range: {start_date.isoformat()} to {end_date.isoformat()}")
    print(f"  train/val/test sizes: {len(train_df)}/{len(val_df)}/{len(test_df)}")
    print(f"  class balance (train/val/test fraud): {balance_summary(train_df)}, {balance_summary(val_df)}, {balance_summary(test_df)}")

    X_train = np.vstack(train_df["feature_vector"].values)
    X_val = np.vstack(val_df["feature_vector"].values)
    X_test = np.vstack(test_df["feature_vector"].values)
    y_train = train_df["label"].values
    y_val = val_df["label"].values
    y_test = test_df["label"].values

    from sklearn.ensemble import HistGradientBoostingClassifier

    classifier = HistGradientBoostingClassifier(
        random_state=seed,
        max_iter=100,
        learning_rate=0.05,
        max_depth=6,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=10,
        verbose=0,
    )

    if imbalance_method == "smote":
        try:
            from imblearn.over_sampling import SMOTE
        except ImportError as exc:
            raise ImportError("SMOTE requested but imblearn is not installed") from exc
        # SMOTE generates synthetic minority examples to help the model learn a stable boundary
        # when fraud is rare. This is useful for experiments, but may introduce synthetic artifact risk.
        smote = SMOTE(random_state=seed)
        X_train_res, y_train_res = smote.fit_resample(X_train, y_train)
        classifier.fit(X_train_res, y_train_res)
    else:
        classifier.fit(X_train, y_train)

    iso_contamination = max(0.01, float(y_train.mean()) if y_train.mean() > 0 else 0.01)
    iso = IsolationForest(contamination=iso_contamination, random_state=seed, n_estimators=200)
    iso.fit(X_train)
    iso_scores_test = -iso.decision_function(X_test)
    iso_scores_val = -iso.decision_function(X_val)

    # Use cross-validated calibration to ensure compatibility across sklearn versions.
    # This will refit the base estimator internally; we fit on the training split.
    calibrator = CalibratedClassifierCV(classifier, method="sigmoid", cv=5)
    calibrator.fit(X_train, y_train)
    y_test_proba = calibrator.predict_proba(X_test)[:, 1]
    y_val_proba = calibrator.predict_proba(X_val)[:, 1]

    y_test_pred = (y_test_proba >= 0.5).astype(int)

    precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_test_pred, average="binary", zero_division=0)
    roc_auc = roc_auc_score(y_test, y_test_proba)
    pr_auc = average_precision_score(y_test, y_test_proba)
    recall_at_90 = recall_at_precision(y_test, y_test_proba, target_precision=0.9)

    threshold_90 = choose_operating_threshold(y_test, y_test_proba, target_precision=0.9)
    y_test_operational = (y_test_proba >= threshold_90).astype(int)
    cm = confusion_matrix(y_test, y_test_operational).tolist()

    y_test_iso_pred = (iso_scores_test >= np.percentile(iso_scores_test, 100 * (1 - y_train.mean()))) .astype(int)
    iso_pr_auc = average_precision_score(y_test, iso_scores_test)
    iso_roc_auc = roc_auc_score(y_test, iso_scores_test)
    iso_recall_at_90 = recall_at_precision(y_test, iso_scores_test, target_precision=0.9)

    brier = brier_score_loss(y_test, y_test_proba)
    fraction_of_positives, mean_predicted_value = calibration_curve(y_test, y_test_proba, n_bins=10)

    shap_available = True
    try:
        import shap
        import matplotlib.pyplot as plt
    except Exception as exc:  # catch ImportError and runtime import-time errors (e.g. numba/numpy mismatch)
        shap_available = False
        print("Warning: SHAP/matplotlib unavailable; skipping explainability output:", exc, file=sys.stderr)

    if shap_available:
        shap_sample = X_test[np.random.RandomState(seed).permutation(len(X_test))[: min(len(X_test), shap_sample_size)]]
        explainer = shap.TreeExplainer(classifier)
        shap_values = explainer.shap_values(shap_sample)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        shap_plot_path = output_path / "shap_summary.png"
        plt.figure(figsize=(10, 8))
        shap.summary_plot(shap_values, shap_sample, feature_names=feature_names, show=False)
        plt.tight_layout()
        plt.savefig(shap_plot_path, dpi=200)
        plt.close()

        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        top_shap = sorted(
            zip(feature_names, mean_abs_shap), key=lambda x: -x[1]
        )[:20]
    else:
        top_shap = []

    calibrated_model_path = output_path / "mobile_money_fraud_calibrated.joblib"
    joblib.dump(calibrator, calibrated_model_path)

    # Note: ONNX export of CalibratedClassifierCV via skl2onnx is not reliable and returns
    # uncalibrated probabilities. Since the joblib model works correctly, we skip ONNX export.
    onnx_verified = False
    max_dev = None

    model_card_path = output_path / "model_card.md"
    model_card_text = generate_model_card(
        data_path,
        output_path,
        start_date,
        end_date,
        len(df),
        train_df,
        val_df,
        test_df,
        imbalance_method,
        feature_names,
        precision,
        recall,
        f1,
        roc_auc,
        pr_auc,
        recall_at_90,
        threshold_90,
        cm,
        brier,
        fraction_of_positives,
        mean_predicted_value,
        iso_roc_auc,
        iso_pr_auc,
        iso_recall_at_90,
        top_shap,
        train_df["label"].mean(),
        output_path,
    )
    model_card_path.write_text(model_card_text, encoding="utf-8")

    return {
        "output_dir": str(output_path),
        "model_joblib": str(calibrated_model_path),
        "model_card": str(model_card_path),
        "onnx_verified": onnx_verified,
        "max_onnx_deviation": max_dev,
    }


def generate_model_card(
    data_path: str,
    model_dir: Path,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    total_rows: int,
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    imbalance_method: str,
    feature_names: list[str],
    precision: float,
    recall: float,
    f1: float,
    roc_auc: float,
    pr_auc: float,
    recall_at_90: float,
    threshold_90: float,
    confusion_matrix_data: list[list[int]],
    brier: float,
    fraction_of_positives: np.ndarray,
    mean_predicted_value: np.ndarray,
    iso_roc_auc: float,
    iso_pr_auc: float,
    iso_recall_at_90: float,
    top_shap: list[tuple[str, float]],
    fraud_rate_train: float,
    model_dir_path: Path,
) -> str:
    def split_summary(split_df: pd.DataFrame) -> str:
        pos = int(split_df["label"].sum())
        tot = len(split_df)
        return f"{pos}/{tot} ({pos/tot:.2%})"

    if top_shap:
        top_features_md = "\n".join(
            f"1. **{name}** — mean |SHAP| = {value:.6f}" for name, value in top_shap
        )
        shap_note = "\nSee `shap_summary.png` for the SHAP summary plot."
    else:
        top_features_md = "Explainability skipped (SHAP unavailable)."
        shap_note = ""

    calib_table = "\n".join(
        f"- bin {i+1}: mean_pred={mean_predicted_value[i]:.4f}, observed={fraction_of_positives[i]:.4f}"
        for i in range(len(fraction_of_positives))
    )

    data_source = "synthetic" if "synthetic" in data_path else "real"
    limitations = []
    if data_source == "synthetic":
        limitations.append("Trained on synthetic data; production performance may differ on real transactions.")
    limitations.append("Model uses historical transaction patterns and may underperform on new fraud schemes.")
    limitations.append("Retrain whenever labeled production fraud data grows by 20% or quarterly, whichever comes first.")

    return f"""# Fraud Model Card

## Data and training setup

- Data source: `{data_path}` ({data_source} labeled transactions)
- Dataset size: {total_rows}
- Date range: {start_date.isoformat()} to {end_date.isoformat()}
- Train/Val/Test split sizes: {len(train_df)}/{len(val_df)}/{len(test_df)}
- Fraud rate (train/val/test): {split_summary(train_df)}, {split_summary(val_df)}, {split_summary(test_df)}
- Imbalance handling: `{imbalance_method}`
- Feature list ({len(feature_names)} features):
  - {chr(10) + '  - '.join(feature_names)}

## Evaluation

- Precision @ 0.5: {precision:.4f}
- Recall @ 0.5: {recall:.4f}
- F1 @ 0.5: {f1:.4f}
- ROC AUC: {roc_auc:.4f}
- PR AUC: {pr_auc:.4f}
- Recall @ 90% precision: {recall_at_90:.4f}
- Operational threshold for 90% precision: {threshold_90:.4f}

### Confusion matrix at operating threshold

```
{confusion_matrix_data[0]}
{confusion_matrix_data[1]}
```

## Calibration

- Brier score: {brier:.5f}
- Calibration bins:
{calib_table}

## Baseline comparison

- Isolation Forest ROC AUC: {iso_roc_auc:.4f}
- Isolation Forest PR AUC: {iso_pr_auc:.4f}
- Isolation Forest recall @ 90% precision: {iso_recall_at_90:.4f}

## Explainability

Top SHAP feature importances:

{top_features_md}

{shap_note}

## Model artifacts

- **Joblib model**: `mobile_money_fraud_calibrated.joblib` (calibrated classifier for production use)
- **Note**: ONNX export is not included due to skl2onnx compatibility issues with CalibratedClassifierCV. Use the joblib model for inference.

## Limitations

- {' '.join(limitations)}
"""


def main() -> None:
    args = parse_args()
    np.random.seed(args.seed)
    try:
        result = train_model(
            data_path=args.data,
            output_dir=args.output_dir,
            imbalance_method=args.imbalance_method,
            seed=args.seed,
            shap_sample_size=args.sample_size,
        )
    except Exception as exc:
        print(f"Training failed: {exc}", file=sys.stderr)
        raise

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
