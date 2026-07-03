from __future__ import annotations
from typing import Dict, Any, Optional
from datetime import datetime
import threading

from ..ml.features import features_for_transaction


class FeatureStore:
    """Simple FeatureStore facade used by the serving checks.

    For production this would wrap Redis + a batch store. For tests we allow
    injecting a snapshot dict per-msisdn.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._snapshots: Dict[str, Dict[str, Any]] = {}

    def put_snapshot(self, msisdn: str, snapshot: Dict[str, Any]) -> None:
        with self._lock:
            self._snapshots[msisdn] = snapshot

    def get_snapshot(self, msisdn: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._snapshots.get(msisdn)

    def get_features(self, msisdn: str, as_of_timestamp: str) -> Dict[str, Any]:
        snap = self.get_snapshot(msisdn)
        amount = 0.0
        if snap:
            amount = snap.get("last_amount") if snap.get("last_amount") is not None else 0.0
        record = {"msisdn": msisdn, "timestamp": as_of_timestamp, "amount": amount}
        res = features_for_transaction(record, feature_store_snapshot=snap)
        return res
