from __future__ import annotations
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class FeatureStore:
    """Feature store abstraction. Default in-memory fallback; Redis-backed impl can be added."""

    def __init__(self, client: Optional[object] = None):
        # client can be a redis.Redis instance or None
        self.client = client
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_features(self, msisdn: str) -> Dict[str, Any]:
        """Return feature dict for msisdn. If external client present, try that first."""
        try:
            if self.client is not None:
                # attempt redis GET (assumes JSON stored)
                try:
                    import json

                    val = self.client.get(f"mm:features:{msisdn}")
                    if val:
                        return json.loads(val)
                except Exception:
                    logger.exception("feature store redis get failed")

            # fallback to in-memory cache
            return self._cache.get(msisdn, {})
        except Exception:
            logger.exception("feature store failure")
            return {}

    def set_features(self, msisdn: str, features: Dict[str, Any]) -> None:
        try:
            self._cache[msisdn] = features
            if self.client is not None:
                try:
                    import json

                    self.client.set(f"mm:features:{msisdn}", json.dumps(features))
                except Exception:
                    logger.exception("feature store redis set failed")
        except Exception:
            logger.exception("feature store set failure")
