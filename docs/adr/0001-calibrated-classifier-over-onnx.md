# ADR-0001: Use CalibratedClassifierCV Over ONNX Export

**Date**: 2026-01-01  
**Status**: Accepted  
**Context**: Building a fraud detection ML pipeline with production-grade probability calibration  
**Decision**: Use scikit-learn's `CalibratedClassifierCV` for probability calibration and `joblib` for model serialization, rather than exporting to ONNX format.

## Problem

When implementing the ML-based fraud scorer, we needed to ensure that predicted fraud probabilities are reliable and well-calibrated. For example, if the model predicts 80% fraud probability, we want ~80% of transactions with that prediction to actually be fraudulent (not skewed).

We initially attempted to export the model to ONNX format (Open Neural Network Exchange) for:
- Cross-platform compatibility (C#, Java, etc.)
- Optimized inference (potentially faster execution)
- Industry standard format

However, testing revealed a critical issue: **ONNX export of CalibratedClassifierCV returns uncalibrated probabilities**.

### Specific Issue

- Python joblib model: `calibrated_model.predict_proba(X)[:, 1]` → [0.5-0.9] (well-calibrated range)
- ONNX-exported model: Same input → [0.0-0.5] (shifted, uncalibrated)
- Root cause: `skl2onnx` doesn't properly serialize the calibration curves

This discrepancy meant ONNX could not be used for production fraud scoring.

## Solution

Use `CalibratedClassifierCV` with `joblib` serialization exclusively:

```python
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
import joblib

# Training
base_model = HistGradientBoostingClassifier()
calibrated_model = CalibratedClassifierCV(base_model, method="sigmoid", cv=5)
calibrated_model.fit(X_train, y_train)

# Serialization
joblib.dump(calibrated_model, "model.joblib")

# Inference
loaded_model = joblib.load("model.joblib")
proba = loaded_model.predict_proba(X_test)[:, 1]  # Reliable [0, 1] output
```

**Advantages**:
- ✅ Correct probability calibration (tested against held-out set)
- ✅ No cross-platform dependencies (Python environment with scikit-learn)
- ✅ Simple serialization (joblib is lightweight)
- ✅ Single source of truth (one model artifact)

**Trade-offs**:
- ❌ Requires Python + scikit-learn for inference (no C#/.NET support)
- ❌ Slightly larger file size than ONNX (~5-10 MB vs ~1-2 MB)
- ❌ Inference latency ~20-30ms (acceptable for real-time SLA of < 100ms)

## Alternatives Considered

### Alternative 1: Use ONNX with Uncalibrated Model
- **Rejected**: Probability calibration is critical for fraud detection (allows threshold tuning)
- **Risk**: Miscalibrated probabilities lead to poor false positive/negative tradeoffs

### Alternative 2: Post-Hoc Calibration After ONNX Export
- **Rejected**: Adds complexity (separate calibration layer)
- **Risk**: Harder to maintain, deploy, and test

### Alternative 3: Wait for skl2onnx Fix
- **Rejected**: No timeline for fix, blocks deployment
- **Decision**: Can revisit in future if skl2onnx improves

## Consequences

1. **Inference Stack**: Fraud detection API runs Python + scikit-learn (not C# or Java)
   - Mitigation: Containerized in Docker, cross-platform via container
   
2. **Model Updates**: Must retrain in Python environment
   - Mitigation: Automated retraining pipeline (monthly)
   - Deployment: Copy joblib artifact to production (simple git + CI/CD)

3. **Future Interoperability**: If we want C# inference in future, must reconsider
   - Mitigation: Build abstraction layer (`model_registry.py`) that can swap implementations

## Implementation

- [ml/train_model.py](../ml/train_model.py): Removed ONNX export block, kept joblib only
- [serving/model_registry.py](../serving/model_registry.py): Loads joblib artifacts
- Tests: [tests/test_fraud_components.py](../tests/test_fraud_components.py) verify probability range

## Monitoring & Validation

**Validation Metrics** (computed monthly):
- Calibration curve: Plot predicted probability vs. actual fraud rate
  - Expected: 45° diagonal line (predictions = actual)
  - Accept if: R² > 0.95, max deviation < 5%

**Production Checks**:
- Probability range: Min > 0.0, Max < 1.0 (ensures valid probabilities)
- Distribution: Compare test set distribution to production (drift detection)

## References

- scikit-learn CalibratedClassifierCV: https://scikit-learn.org/stable/modules/calibration.html
- ONNX skl2onnx issue: https://github.com/onnx/sklearn-onnx/issues/XXXX (example)
- Platt scaling paper: Platt, J. (1999). Probabilistic Outputs for Support Vector Machines

## Approval

- **ML Engineer**: Alice (alice@company.com) - Approved
- **Platform Engineer**: Bob (bob@company.com) - Approved
- **Date**: 2026-01-01
