from __future__ import annotations
from typing import Dict, Any, Optional
import time

from .base import FraudCheck, CheckResult, CheckState


class SimSwapCorrelator(FraudCheck):
    def __init__(self, swap_store: Optional[Dict[str, float]] = None, lookback_seconds: int = 3600, amount_threshold: float = 1000.0, name: str = "sim_swap") -> None:
        self.swap_store = swap_store if swap_store is not None else {}
        self.lookback = lookback_seconds
        self.amount_threshold = amount_threshold
        self.name = name

    def record_swap(self, msisdn: str, ts: float) -> None:
        self.swap_store[msisdn] = ts

    def evaluate(self, txn: Dict[str, Any], context: Dict[str, Any]) -> CheckResult:
        msisdn = txn.get("msisdn")
        amount = float(txn.get("amount", 0.0))
        now = time.time()
        try:
            last_swap = self.swap_store.get(msisdn)
            if last_swap is None:
                return CheckResult(name=self.name, score=0.0, triggered=False, reason="no_swap_on_record", weight=1.0, state=CheckState.OK)

            if now - last_swap <= self.lookback and amount >= self.amount_threshold:
                return CheckResult(name=self.name, score=0.9, triggered=True, reason="recent_swap_and_high_amount", weight=1.0, state=CheckState.TRIGGERED)
            else:
                # swap feed may be stale vs no-swap
                if now - last_swap > self.lookback * 10:
                    return CheckResult(name=self.name, score=0.0, triggered=False, reason="swap_feed_stale", weight=0.5, state=CheckState.UNKNOWN)
                return CheckResult(name=self.name, score=0.1, triggered=False, reason="swap_not_recent_or_amount_low", weight=0.5, state=CheckState.OK)
        except Exception as exc:
            return CheckResult(name=self.name, score=0.0, triggered=False, reason=f"error:{exc}", weight=1.0, state=CheckState.UNKNOWN)
 
