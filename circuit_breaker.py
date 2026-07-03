from __future__ import annotations
import time
from enum import Enum
from typing import Callable


class State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, fail_max: int = 3, reset_timeout: float = 5.0) -> None:
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self._state = State.CLOSED
        self._fail_count = 0
        self._opened_at = 0.0

    def call(self, func: Callable, *args, **kwargs):
        now = time.time()
        if self._state == State.OPEN:
            if now - self._opened_at > self.reset_timeout:
                self._state = State.HALF_OPEN
            else:
                raise RuntimeError("circuit_open")

        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            self._fail_count += 1
            if self._fail_count >= self.fail_max:
                self._state = State.OPEN
                self._opened_at = time.time()
            raise
        else:
            # success
            self._fail_count = 0
            if self._state == State.HALF_OPEN:
                self._state = State.CLOSED
            return result

    @property
    def state(self) -> State:
        return self._state
