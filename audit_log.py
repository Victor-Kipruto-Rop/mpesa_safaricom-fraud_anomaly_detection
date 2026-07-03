from __future__ import annotations
from typing import Dict, Any
import json
import os
import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AuditLog:
    """Immutable audit log implemented as append-only JSONL files and idempotency guard.

    Note: For production, replace with an encrypted, access-controlled store (S3 with KMS + Lakehouse).
    """

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self._lock = threading.RLock()
        # simple in-memory set to avoid duplicate writes within this process
        self._written = set()

    def _path_for_day(self, when: datetime) -> str:
        name = when.strftime("fraud_audit_%Y-%m-%d.jsonl")
        return os.path.join(self.base_dir, name)

    def persist(self, record: Dict[str, Any]) -> None:
        txn_id = record.get("txn_id") or record.get("transaction_id")
        if not txn_id:
            raise ValueError("record must include txn_id")

        with self._lock:
            if txn_id in self._written:
                logger.debug("audit record already persisted: %s", txn_id)
                return
            path = self._path_for_day(datetime.utcnow())
            try:
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, default=str) + "\n")
                # mark written
                self._written.add(txn_id)
            except Exception:
                logger.exception("failed to persist audit record %s", txn_id)
