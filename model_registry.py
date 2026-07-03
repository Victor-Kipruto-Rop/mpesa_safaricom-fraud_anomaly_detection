from __future__ import annotations
from typing import Optional, Dict, Any
import threading
import time as _time
import os
import logging

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Simple model registry supporting joblib and ONNX runtimes.

    Provides thread-safe in-memory model cache and hot-swap support.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._models: Dict[str, Dict[str, Any]] = {}

    def load_joblib(self, name: str, path: str, version: Optional[str] = None) -> None:
        try:
            import joblib

            m = joblib.load(path)
            with self._lock:
                self._models[name] = {"model": m, "version": version or os.path.basename(path), "backend": "joblib"}
        except Exception as e:
            logger.exception("failed to load joblib model: %s", e)

    def load_onnx(self, name: str, path: str, version: Optional[str] = None) -> None:
        try:
            import onnxruntime as ort

            sess = ort.InferenceSession(path)
            with self._lock:
                self._models[name] = {"model": sess, "version": version or os.path.basename(path), "backend": "onnx"}
        except Exception as e:
            logger.exception("failed to load onnx model: %s", e)

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._models.get(name)

    def hot_swap(self, name: str, loader_callable) -> None:
        """Loader callable should return dict with keys model, version, backend."""
        try:
            new = loader_callable()
            with self._lock:
                self._models[name] = new
        except Exception:
            logger.exception("hot swap failed for %s", name)
