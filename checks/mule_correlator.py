from __future__ import annotations
from typing import Dict, Any, Set
import time

from .base import FraudCheck, CheckResult, CheckState


class MuleAccountCorrelator(FraudCheck):
    def __init__(self, window_seconds: int = 3600, sender_threshold: int = 5, name: str = "mule_correlator") -> None:
        self.window = window_seconds
        self.sender_threshold = sender_threshold
        self.name = name
        # in-memory: receiver -> list of (sender, timestamp)
        self._store: Dict[str, list[tuple[str, float]]] = {}
        # light adjacency: a mapping of sender -> set(connected senders)
        self._adj: Dict[str, Set[str]] = {}

    def add_historical_connection(self, a: str, b: str) -> None:
        self._adj.setdefault(a, set()).add(b)
        self._adj.setdefault(b, set()).add(a)

    def _prune(self, receiver: str) -> None:
        now = time.time()
        items = self._store.get(receiver, [])
        items = [(s, ts) for (s, ts) in items if now - ts <= self.window]
        self._store[receiver] = items

    def evaluate(self, txn: Dict[str, Any], context: Dict[str, Any]) -> CheckResult:
        receiver = txn.get("receiver") or txn.get("to") or txn.get("dest")
        sender = txn.get("msisdn") or txn.get("from")
        amount = float(txn.get("amount", 0.0))
        now = time.time()

        try:
            self._store.setdefault(receiver, []).append((sender, now))
            self._prune(receiver)
            senders = {s for s, _ in self._store[receiver]}

            if len(senders) < self.sender_threshold:
                return CheckResult(name=self.name, score=0.0, triggered=False, reason="not_enough_senders", weight=0.6, state=CheckState.OK)

            # check "previously unconnected": ensure pairwise senders have no adj edges
            unconnected_count = 0
            senders_list = list(senders)
            for i in range(len(senders_list)):
                for j in range(i + 1, len(senders_list)):
                    a = senders_list[i]
                    b = senders_list[j]
                    if b not in self._adj.get(a, set()):
                        unconnected_count += 1

            # heuristic: if a large fraction of sender-pairs are unconnected, suspect mule
            total_pairs = max(1, (len(senders_list) * (len(senders_list) - 1)) // 2)
            frac_unconnected = unconnected_count / total_pairs
            triggered = frac_unconnected > 0.6
            score = 0.7 if triggered else 0.2
            reason = "mule_suspected" if triggered else "mule_not_suspected"
            state = CheckState.TRIGGERED if triggered else CheckState.OK
            return CheckResult(name=self.name, score=score, triggered=triggered, reason=reason, weight=0.7, state=state)
        except Exception as exc:
            return CheckResult(name=self.name, score=0.0, triggered=False, reason=f"error:{exc}", weight=0.7, state=CheckState.UNKNOWN)
