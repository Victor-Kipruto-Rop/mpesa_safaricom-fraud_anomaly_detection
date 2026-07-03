from __future__ import annotations
from typing import Dict, Any
import json
import logging
import os

logger = logging.getLogger(__name__)


class DeadLetterQueue:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def push(self, payload: Dict[str, Any], reason: str) -> None:
        path = os.path.join(self.base_dir, "dlq.jsonl")
        entry = {"payload": payload, "reason": reason}
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, default=str) + "\n")
        except Exception:
            logger.exception("failed to write dlq")
