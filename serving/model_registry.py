from __future__ import annotations
import threading
from dataclasses import dataclass
from typing import Optional, Any
from pathlib import Path
import joblib
import numpy as np

try:
    import onnxruntime as ort
except Exception:
    ort = None


@dataclass
class LoadedModel:
    version: str
    joblib_obj: Any
    onnx_sess: Optional[Any]

    def predict_proba_python(self, X: np.ndarray) -> np.ndarray:
        return self.joblib_obj.predict_proba(X)[:, 1]

    def predict_proba_onnx(self, X: np.ndarray) -> np.ndarray:
        if self.onnx_sess is None:
            raise RuntimeError("ONNX session not loaded")
        input_name = self.onnx_sess.get_inputs()[0].name
        out = self.onnx_sess.run(None, {input_name: X.astype(np.float32)})
        if isinstance(out, dict):
            out = list(out.values())
        if isinstance(out, list) and len(out) >= 2:
            prob_output = out[1]
            # handle list-of-dicts output
            if isinstance(prob_output, list) and len(prob_output) == X.shape[0] and isinstance(prob_output[0], dict):
                return np.array([d.get(1, d.get(0, 0.0)) for d in prob_output], dtype=np.float32)
            return np.asarray(prob_output) if np.asarray(prob_output).ndim == 1 else np.asarray(prob_output)[:, -1]
        return np.asarray(out[-1])


class ModelRegistry:
    """Loads and serves champion/challenger models with hot-swap support."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._champion: Optional[LoadedModel] = None
        self._challenger: Optional[LoadedModel] = None

    def load_from_paths(self, version: str, joblib_path: str, onnx_path: str | None = None) -> LoadedModel:
        jb = joblib.load(joblib_path)
        onnx_sess = None
        if onnx_path and ort is not None:
            onnx_sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

        return LoadedModel(version=version, joblib_obj=jb, onnx_sess=onnx_sess)

    def register_champion(self, model: LoadedModel) -> None:
        with self._lock:
            self._champion = model

    def register_challenger(self, model: LoadedModel) -> None:
        with self._lock:
            self._challenger = model

    def hot_swap_champion(self, model: LoadedModel) -> None:
        # atomic swap
        with self._lock:
            self._champion = model

    def get_champion(self) -> Optional[LoadedModel]:
        with self._lock:
            return self._champion

    def get_challenger(self) -> Optional[LoadedModel]:
        with self._lock:
            return self._challenger
