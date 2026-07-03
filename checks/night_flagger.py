from __future__ import annotations
from typing import Dict, Any
from datetime import datetime, timezone, timedelta

from .base import FraudCheck, CheckResult, CheckState


class NightTransactionFlagger(FraudCheck):
    def __init__(self, start_hour: int = 0, end_hour: int = 6, name: str = "night_flagger") -> None:
        self.start = start_hour
        self.end = end_hour
        self.name = name

    def _local_hour(self, ts: str, tz_offset_minutes: int = 0) -> int:
        try:
            dt = datetime.fromisoformat(ts)
        except Exception:
            return 2
        dt = dt + timedelta(minutes=tz_offset_minutes)
        return dt.hour

    def evaluate(self, txn: Dict[str, Any], context: Dict[str, Any]) -> CheckResult:
        ts = txn.get("timestamp")
        try:
            tz_offset = context.get("tz_offset_minutes", 0)
            hour = self._local_hour(ts, tz_offset)
            in_night = False
            if self.start <= self.end:
                in_night = self.start <= hour < self.end
            else:
                in_night = hour >= self.start or hour < self.end

            score = 0.3 if in_night else 0.0
            reason = "off_hours" if in_night else "day_hours"
            return CheckResult(name=self.name, score=score, triggered=in_night, reason=reason, weight=0.3, state=CheckState.TRIGGERED if in_night else CheckState.OK)
        except Exception as exc:
            return CheckResult(name=self.name, score=0.0, triggered=False, reason=f"error:{exc}", weight=0.3, state=CheckState.UNKNOWN)
 
