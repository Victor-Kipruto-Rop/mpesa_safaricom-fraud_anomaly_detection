from __future__ import annotations
from typing import Dict, Any, List
from .checks.base import FraudCheck, CheckResult
from .aggregator import FraudScoreAggregator, FraudScoreResult


class ConsolidatedFraudDetectionEngine:
    def __init__(self, config: Dict[str, Any], checks_registry: Dict[str, List[FraudCheck]], aggregator: FraudScoreAggregator):
        self.config = config
        # checks_registry maps domain -> list of FraudCheck
        self.checks_registry = checks_registry
        self.aggregator = aggregator
        # simple sinks
        self.audit_log: List[Dict[str, Any]] = []
        self.review_sink: List[Dict[str, Any]] = []

    def score(self, txn: Dict[str, Any]) -> FraudScoreResult:
        domain = txn.get("domain", "mobile_money")
        if domain == "mobile_money":
            return self.score_mobile_money_transaction(txn)
        else:
            # fallback to mobile_money behavior if unknown domain
            return self.score_mobile_money_transaction(txn)

    def validate_raw_transaction(self, txn: Dict[str, Any]) -> bool:
        required = {"txn_id", "msisdn", "amount", "timestamp"}
        missing = required - set(txn.keys())
        return len(missing) == 0

    def score_mobile_money_transaction(self, txn: Dict[str, Any]) -> FraudScoreResult:
        # validate
        if not self.validate_raw_transaction(txn):
            # malformed -> raise or return a result with UNKNOWN
            res = FraudScoreResult(score=0.0, decision=self.aggregator.config.get("default_decision", "REVIEW"), explanation={"error": "malformed"})
            # write audit
            self.audit_log.append({"txn": txn, "result": res})
            return res

        checks = self.checks_registry.get("mobile_money", [])
        context: Dict[str, Any] = {}
        results: List[CheckResult] = []
        for c in checks:
            try:
                r = c.evaluate(txn, context)
            except Exception as exc:
                r = CheckResult(name=getattr(c, "name", type(c).__name__), score=0.0, triggered=False, reason=f"error:{exc}", weight=0.0, state=None)
            results.append(r)

        score_result = self.aggregator.aggregate(results)

        # audit log always
        audit_entry = {"txn": txn, "checks": [vars(r) for r in results], "score": score_result.score, "decision": score_result.decision.value, "explanation": score_result.explanation}
        # include shadow scores if present
        if context.get("__shadow_scores__"):
            audit_entry["shadow_scores"] = context["__shadow_scores__"]
        self.audit_log.append(audit_entry)

        if score_result.decision in (score_result.decision.__class__.REVIEW, score_result.decision.__class__.BLOCK):
            self.review_sink.append(audit_entry)

        return score_result

    def _record_failure(self) -> None:
        now = datetime.utcnow()
        with self._circuit_lock:
            self._circuit_state["failure_timestamps"].append(now)
            window_start = now - timedelta(seconds=self.config.circuit_breaker_window_seconds)
            self._circuit_state["failure_timestamps"] = [t for t in self._circuit_state["failure_timestamps"] if t >= window_start]
            if len(self._circuit_state["failure_timestamps"]) >= self.config.circuit_breaker_failure_threshold:
                self._circuit_state["opened_at"] = now
                logger.warning("fraud engine circuit breaker opened", failures=len(self._circuit_state["failure_timestamps"]))

    def _is_circuit_open(self) -> bool:
        with self._circuit_lock:
            opened_at = self._circuit_state["opened_at"]
            if not opened_at:
                return False
            elapsed = (datetime.utcnow() - opened_at).total_seconds()
            if elapsed >= self.config.circuit_breaker_recovery_seconds:
                self._circuit_state["failure_timestamps"] = []
                self._circuit_state["opened_at"] = None
                logger.info("fraud engine circuit breaker closed")
                return False
            return True

    def reconcile_batch(self, records: list[Dict[str, Any]], audit_dir: Optional[str] = None) -> Dict[str, Any]:
        if not self.config.enable_batch_reconciliation:
            raise RuntimeError("batch reconciliation disabled by configuration")

        BATCH_RECONCILIATION_TOTAL.inc()
        audit_dir = audit_dir or self.audit.base_dir
        reconciled = 0
        missing = 0
        details = []

        for record in records:
            txn_id = record.get("txn_id") or record.get("transaction_id")
            if not txn_id:
                missing += 1
                details.append({"record": record, "status": "missing_txn_id"})
                continue

            audit_file_pattern = os.path.join(audit_dir, "fraud_audit_*.jsonl")
            found = False
            for audit_file in glob.glob(audit_file_pattern):
                with open(audit_file, "r", encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            existing = json.loads(line)
                            if existing.get("txn_id") == txn_id:
                                found = True
                                break
                        except Exception:
                            continue
                if found:
                    break

            if found:
                reconciled += 1
                details.append({"txn_id": txn_id, "status": "matched"})
            else:
                missing += 1
                BATCH_RECONCILIATION_MISSING_TOTAL.inc()
                details.append({"txn_id": txn_id, "status": "missing"})

        return {
            "requested": len(records),
            "reconciled": reconciled,
            "missing": missing,
            "audit_dir": audit_dir,
            "details": details,
        }
"""Simple mobile-money fraud detection engine.

Features:
- optional ML scoring (joblib model)
- velocity spike detection (>N txns in window)
- SIM swap + high-value correlation
- night transaction flags
- configurable thresholds via config.DEFAULTS or passed settings
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, time as dtime
from typing import List, Optional, Dict, Any
import os

try:
    import joblib
except Exception:
    joblib = None

from .config import DEFAULTS


@dataclass
class FraudAlert:
    transaction_id: str
    detected_type: str  # MPESA_FRAUD, NORMAL
    risk_score: float
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    rules_triggered: List[str]
    timestamp: str
    institution: Optional[str]
    alert_message: Optional[str]


class MobileMoneyFraudEngine:
    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        self.settings = DEFAULTS.copy()
        if settings:
            self.settings.update(settings)

        self.model = None
        model_path = self.settings.get("ml_model_path")
        if model_path and joblib is not None and os.path.exists(model_path):
            try:
                self.model = joblib.load(model_path)
            except Exception:
                self.model = None

    def _parse_ts(self, ts):
        if isinstance(ts, datetime):
            return ts
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            # fallback
            return datetime.utcfromtimestamp(float(ts))

    def score_mobile_money_transaction(self, txn: Dict[str, Any], history: Optional[List[Dict[str, Any]]] = None) -> FraudAlert:
        """Score a single mobile-money transaction.

        txn: dict with keys: transaction_id, account_id, msisdn, sim_serial, amount, timestamp
        history: recent transactions for the same account or msisdn (list of txn dicts)
        """
        rules = []
        risk = 0.0

        # Basic fields
        txn_id = str(txn.get("transaction_id") or txn.get("id") or "unknown")
        institution = txn.get("institution")
        ts = self._parse_ts(txn.get("timestamp") or txn.get("time") or txn.get("ts") or datetime.utcnow())
        amount = float(txn.get("amount") or 0.0)

        # ML scoring (if model available)
        if self.model is not None:
            try:
                # Model should accept a feature vector or dict-like preprocess externally
                features = txn.get("features")
                if features is None:
                    # lightweight feature extraction
                    features = [amount]
                score = float(self.model.predict_proba([features])[0][-1]) if hasattr(self.model, "predict_proba") else float(self.model.predict([features])[0])
                risk = max(risk, score)
                rules.append("ML_MODEL")
            except Exception:
                # ignore model errors
                pass

        # Velocity detection: count txns within window
        if history:
            window = timedelta(seconds=int(self.settings.get("velocity_window_seconds", 60)))
            cutoff = ts - window
            recent = [h for h in history if self._parse_ts(h.get("timestamp")) >= cutoff]
            if len(recent) + 1 >= int(self.settings.get("velocity_txn_threshold", 10)):
                rules.append("VELOCITY_SPIKE")
                # scale risk by number over threshold
                excess = (len(recent) + 1) / float(self.settings.get("velocity_txn_threshold", 10))
                risk = max(risk, min(0.9, 0.2 * excess))

        # SIM swap + high value correlation
        if history:
            # find other txns with same account but different sim_serial
            sim = txn.get("sim_serial")
            other_sim_high = False
            for h in history:
                if h.get("account_id") == txn.get("account_id") and h.get("sim_serial") and sim and h.get("sim_serial") != sim and float(h.get("amount") or 0) >= float(self.settings.get("high_value_amount", 10000.0)):
                    other_sim_high = True
                    break
            if other_sim_high and amount >= float(self.settings.get("high_value_amount", 10000.0)):
                rules.append("SIM_SWAP_HIGH_VALUE")
                risk = max(risk, 0.95)

        # Night transaction flags
        night_start: time = self.settings.get("night_start")
        night_end: time = self.settings.get("night_end")
        local_time = ts.time()
        is_night = False
        if night_start <= night_end:
            is_night = (local_time >= night_start and local_time < night_end)
        else:
            # overnight wrap
            is_night = (local_time >= night_start or local_time < night_end)

        if is_night and amount >= (float(self.settings.get("high_value_amount", 10000.0)) * 0.1):
            rules.append("NIGHT_TXN")
            risk = max(risk, 0.4)

        # Finalize risk and severity
        risk = float(min(1.0, risk))

        if risk >= 0.9:
            severity = "CRITICAL"
        elif risk >= 0.7:
            severity = "HIGH"
        elif risk >= 0.4:
            severity = "MEDIUM"
        elif risk > 0:
            severity = "LOW"
        else:
            severity = "NORMAL"

        detected_type = "MPESA_FRAUD" if rules else "NORMAL"

        return FraudAlert(
            transaction_id=txn_id,
            detected_type=detected_type,
            risk_score=risk,
            severity=severity,
            rules_triggered=rules,
            timestamp=ts.isoformat(),
            institution=institution,
            alert_message=None,
        )

    def export_alert(self, alert: FraudAlert, path: str):
        # simple CSV append
        import csv

        exists = os.path.exists(path)
        with open(path, "a", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(asdict(alert).keys()))
            if not exists:
                writer.writeheader()
            writer.writerow(asdict(alert))
