from __future__ import annotations
from typing import Dict, Any
import numpy as np

from ..serving.model_registry import ModelRegistry
from ..serving.feature_store import FeatureStore
from .base import FraudCheck, CheckResult, CheckState


class MLFraudScorer(FraudCheck):
    def __init__(self, model_registry: ModelRegistry, feature_store: FeatureStore, name: str = "ml_scorer") -> None:
        self.model_registry = model_registry
        self.feature_store = feature_store
        self.name = name

    def evaluate(self, txn: Dict[str, Any], context: Dict[str, Any]) -> CheckResult:
        msisdn = txn.get("msisdn")
        ts = txn.get("timestamp")
        try:
            snap = self.feature_store.get_snapshot(msisdn)
            fv = self.feature_store.get_features(msisdn, ts)["vector"]
            X = np.asarray([fv], dtype=np.float32)

            champion = self.model_registry.get_champion()
            challenger = self.model_registry.get_challenger()

            champion_score = None
            challenger_score = None
            if champion:
                try:
                    champion_score = champion.predict_proba_onnx(X) if champion.onnx_sess is not None else champion.predict_proba_python(X)
                    if isinstance(champion_score, np.ndarray) and champion_score.ndim > 0:
                        champion_score = float(champion_score.ravel()[0])
                except Exception:
                    champion_score = None

            if challenger:
                try:
                    challenger_score = challenger.predict_proba_onnx(X) if challenger.onnx_sess is not None else challenger.predict_proba_python(X)
                    if isinstance(challenger_score, np.ndarray) and challenger_score.ndim > 0:
                        challenger_score = float(challenger_score.ravel()[0])
                except Exception:
                    challenger_score = None

            score = float(champion_score) if champion_score is not None else (float(challenger_score) if challenger_score is not None else 0.0)
            triggered = score > 0.5
            reason = "ml_model" + (":champion" if champion_score is not None else ":fallback")
            # Log challenger separately in context for downstream recording
            if "__shadow_scores__" not in context:
                context["__shadow_scores__"] = {}
            context["__shadow_scores__"][self.name] = {"champion": champion_score, "challenger": challenger_score}
            return CheckResult(name=self.name, score=score, triggered=triggered, reason=reason, weight=1.0, state=CheckState.TRIGGERED if triggered else CheckState.OK)
        except Exception as exc:
            return CheckResult(name=self.name, score=0.0, triggered=False, reason=f"error:{exc}", weight=1.0, state=CheckState.UNKNOWN)
 
