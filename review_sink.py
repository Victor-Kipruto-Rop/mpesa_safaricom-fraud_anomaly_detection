from __future__ import annotations
from typing import Dict, Any
import json
import os
import logging

logger = logging.getLogger(__name__)


class ReviewSink:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def push(self, record: Dict[str, Any]) -> None:
        path = os.path.join(self.base_dir, "review_queue.jsonl")
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
        except Exception:
            logger.exception("failed to push review record")
