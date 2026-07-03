from __future__ import annotations
from typing import Callable, Optional
import threading
import logging
from .config import FraudConfig

logger = logging.getLogger(__name__)


class ConfigManager:
    def __init__(self, loader: Callable[[], dict], poll_interval: int = 30):
        self.loader = loader
        self.poll_interval = poll_interval
        self._config = FraudConfig.from_store(loader)
        self._lock = threading.RLock()
        self._timer: Optional[threading.Timer] = None
        self._running = False

    @property
    def config(self) -> FraudConfig:
        with self._lock:
            return self._config

    def start(self) -> None:
        self._running = True
        self._schedule()

    def stop(self) -> None:
        self._running = False
        if self._timer:
            self._timer.cancel()

    def _schedule(self):
        self._timer = threading.Timer(self.poll_interval, self._reload)
        self._timer.daemon = True
        self._timer.start()

    def _reload(self):
        try:
            new = FraudConfig.from_store(self.loader)
            with self._lock:
                if new.config_version != self._config.config_version:
                    logger.info("config version changed %s -> %s", self._config.config_version, new.config_version)
                    self._config = new
        except Exception:
            logger.exception("config reload failed")
        finally:
            if self._running:
                self._schedule()
