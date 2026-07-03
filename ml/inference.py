"""Inference wrapper that uses ModelRegistry to load the exported model and predict.

Supports legacy single-model (joblib/onnx) and the new stacked model bundle saved by the training pipeline.
"""
from __future__ import annotations
from typing import Dict, Any
from ..model_registry import ModelRegistry
import numpy as np
import logging

logger = logging.getLogger(__name__)


class InferenceWrapper:
    def __init__(self, registry: ModelRegistry, model_name: str = "mobile_money_fraud_v1"):
        self.registry = registry
        self.model_name = model_name

    def _score_with_bundle(self, bundle: Dict[str, Any], features_arr: np.ndarray) -> float:
        # bundle contains meta_clf, base_clf, calibrator (optional), isolation_forest (optional)
        iso = bundle.get("isolation_forest")
        clf = bundle.get("base_clf")
        calibrator = bundle.get("calibrator")
        meta = bundle.get("meta_clf")

        # compute iso score if available
        if iso is not None:
            try:
                iso_score = float(-iso.decision_function(features_arr.reshape(1, -1))[0])
            except Exception:
                iso_score = 0.0
        else:
            iso_score = 0.0

        # augment features for base clf (base clf expects iso appended)
        arr_aug = np.hstack([features_arr, np.array([iso_score])])

        if calibrator is not None:
            try:
                base_proba = float(calibrator.predict_proba(arr_aug.reshape(1, -1))[0, 1])
            except Exception:
                base_proba = float(clf.predict_proba(arr_aug.reshape(1, -1))[0, 1])
        else:
            base_proba = float(clf.predict_proba(arr_aug.reshape(1, -1))[0, 1])

        # meta model takes [base_proba, iso_score]
        meta_in = np.vstack([[base_proba, iso_score]])
        try:
            stacked = float(meta.predict_proba(meta_in)[0, 1])
        except Exception:
            stacked = base_proba
        return max(0.0, min(1.0, stacked))

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        entry = self.registry.get(self.model_name)
        if not entry:
            raise RuntimeError("model not found in registry")
        model = entry.get("model")
        version = entry.get("version")
        try:
            # ONNX runtime path
            if entry.get("backend") == "onnx":
                sess = model
                input_name = sess.get_inputs()[0].name
                import numpy as _np
                arr = _np.array([features], dtype=_np.float32)
                out = sess.run(None, {input_name: arr})
                score = float(out[0][0][1]) if hasattr(out[0][0], "__len__") else float(out[0][0])
            else:
                # joblib-loaded object may be a bundled dict (stacked model) or a plain sklearn model
                if isinstance(model, dict) and ("meta_clf" in model or "base_clf" in model):
                    arr = np.array(features, dtype=float)
                    score = self._score_with_bundle(model, arr)
                else:
                    arr = np.array([features])
                    if hasattr(model, "predict_proba"):
                        score = float(model.predict_proba(arr)[0][-1])
                    else:
                        score = float(model.predict(arr)[0])
            return {"score": max(0.0, min(1.0, score)), "model_version": version}
        except Exception:
            logger.exception("inference failed")
            return {"score": 0.0, "model_version": version, "error": True}
