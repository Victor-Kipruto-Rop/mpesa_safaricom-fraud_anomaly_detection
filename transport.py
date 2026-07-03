from __future__ import annotations
from typing import Protocol, Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


class ScorePublisher(Protocol):
    def publish(self, topic: str, message: Dict[str, Any]) -> None:
        ...


class FilePublisher:
    def __init__(self, path: str):
        self.path = path

    def publish(self, topic: str, message: Dict[str, Any]) -> None:
        try:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"topic": topic, "message": message}, default=str) + "\n")
        except Exception:
            logger.exception("file publish failed")


class KafkaPublisher:
    def __init__(self, bootstrap_servers: str, topic: str, producer=None):
        # producer can be injected for testing; otherwise lazy import kafka-python
        self.topic = topic
        if producer is not None:
            self._producer = producer
        else:
            try:
                from kafka import KafkaProducer

                self._producer = KafkaProducer(bootstrap_servers=bootstrap_servers, value_serializer=lambda v: json.dumps(v).encode("utf-8"))
            except Exception:
                logger.exception("kafka producer init failed")
                self._producer = None

    def publish(self, topic: str, message: Dict[str, Any]) -> None:
        if not self._producer:
            logger.error("kafka producer not available")
            return
        try:
            self._producer.send(topic or self.topic, message)
        except Exception:
            logger.exception("kafka publish failed")
