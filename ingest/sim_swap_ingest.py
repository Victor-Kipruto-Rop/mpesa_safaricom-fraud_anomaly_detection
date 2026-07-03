from __future__ import annotations
from typing import Dict, Any, Iterable
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


def ingest_sim_swap_events(stream: Iterable[Dict[str, Any]], redis_client) -> None:
    """Simple ingest: stream of events -> persist raw and update lookup key in redis.

    Each event: {msisdn, swap_timestamp, source, confidence}
    """
    for ev in stream:
        try:
            # persist raw zone is responsibility of caller; here we update lookup
            msisdn = ev.get("msisdn")
            key = f"mm:sim_swap:{msisdn}"
            redis_client.set(key, json.dumps(ev))
        except Exception:
            logger.exception("failed to ingest sim swap event for %s", ev.get("msisdn"))
