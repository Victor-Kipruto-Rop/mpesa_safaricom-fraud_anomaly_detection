"""Batch reconciliation: re-score a set of scored transactions and report divergences."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Iterable

from .engine import ConsolidatedFraudDetectionEngine
from .aggregator import FraudScoreAggregator


def reconcile(audit_jsonl: Iterable[str], engine: ConsolidatedFraudDetectionEngine) -> dict:
    total = 0
    divergences = 0
    details = []
    for line in audit_jsonl:
        rec = json.loads(line)
        total += 1
        orig_decision = rec.get("decision") or rec.get("aggregated", {}).get("decision")
        txn = rec.get("txn") or rec.get("input") or rec.get("transaction")
        if not txn:
            continue
        new = engine.score(txn)
        new_dec = new.decision.value if hasattr(new, "decision") else new.get("decision")
        if str(orig_decision) != str(new_dec):
            divergences += 1
            details.append({"txn_id": txn.get("txn_id"), "orig": orig_decision, "new": new_dec})

    return {"total": total, "divergences": divergences, "details_sample": details[:20], "divergence_rate": divergences / total if total else 0.0}


def reconcile_file(path: str, engine: ConsolidatedFraudDetectionEngine) -> dict:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        return reconcile(f, engine)
