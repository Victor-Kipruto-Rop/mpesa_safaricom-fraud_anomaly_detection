from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any


class CheckState(Enum):
    OK = "ok"
    TRIGGERED = "triggered"
    UNKNOWN = "unknown"


@dataclass
class CheckResult:
    name: str
    score: float
    triggered: bool
    reason: str
    weight: float
    state: CheckState


class FraudCheck:
    def evaluate(self, txn: dict, context: dict) -> CheckResult:
        raise NotImplementedError()
 
