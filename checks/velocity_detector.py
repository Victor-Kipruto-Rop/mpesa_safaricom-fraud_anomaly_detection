from __future__ import annotations
from typing import Dict, Any
import time

from .base import FraudCheck, CheckResult, CheckState


class VelocityDetector(FraudCheck):
    def __init__(self, short_window_sec: int = 60 * 60, long_window_sec: int = 24 * 3600, k: float = 3.0, name: str = "velocity") -> None:
        self.short_window = short_window_sec
        self.long_window = long_window_sec
        self.k = k
        self.name = name
        # in-memory per-msisdn timestamps
        self._store: Dict[str, list[float]] = {}

    def _prune(self, msisdn: str) -> None:
        now = time.time()
        items = self._store.get(msisdn, [])
        items = [t for t in items if now - t <= self.long_window]
        self._store[msisdn] = items

    def evaluate(self, txn: Dict[str, Any], context: Dict[str, Any]) -> CheckResult:
        msisdn = txn.get("msisdn")
        now = time.time()
        try:
            self._store.setdefault(msisdn, []).append(now)
            self._prune(msisdn)
            items = self._store[msisdn]
            short_count = len([t for t in items if now - t <= self.short_window])
            long_count = len(items)

            # derive adaptive threshold from context feature snapshot if present
            snap = context.get("feature_snapshot") or {}
            mean_short = snap.get("mean_short", 0.0)
            std_short = snap.get("std_short", 0.0)
            threshold = mean_short + self.k * std_short if mean_short or std_short else 10

            triggered = short_count > threshold
            score = min(1.0, short_count / (threshold + 1e-9))
            reason = f"burst:{short_count}>thr:{threshold:.2f}"
            state = CheckState.TRIGGERED if triggered else CheckState.OK
            return CheckResult(name=self.name, score=score, triggered=triggered, reason=reason, weight=0.8, state=state)
        except Exception as exc:
            return CheckResult(name=self.name, score=0.0, triggered=False, reason=f"error:{exc}", weight=0.8, state=CheckState.UNKNOWN)
 
