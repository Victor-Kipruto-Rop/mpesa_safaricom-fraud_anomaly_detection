from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import Dict
from datetime import time


class DecisionThresholds(BaseModel):
    allow: float = Field(0.0, ge=0.0, le=1.0)
    review: float = Field(0.5, ge=0.0, le=1.0)
    block: float = Field(0.8, ge=0.0, le=1.0)


class FraudConfig(BaseModel):
    # velocity
    velocity_window_seconds: int = Field(60, ge=1)
    velocity_txn_threshold: int = Field(10, ge=1)
    burst_window_seconds: int = Field(10, ge=1)
    burst_txn_threshold: int = Field(5, ge=1)

    # sim swap
    sim_swap_lookback_hours: int = Field(48, ge=1)
    high_value_amount: float = Field(10000.0, ge=0.0)

    # night window
    night_start: str = Field("00:00")
    night_end: str = Field("05:00")
    default_timezone: str = Field("Africa/Nairobi")

    # ml
    ml_model_enabled: bool = Field(True)
    ml_score_cutoff: float = Field(0.7, ge=0.0, le=1.0)

    # circuit breaker
    circuit_breaker_failure_threshold: int = Field(3, ge=1)
    circuit_breaker_window_seconds: int = Field(60, ge=1)
    circuit_breaker_recovery_seconds: int = Field(120, ge=1)

    # batch reconciliation
    enable_batch_reconciliation: bool = Field(True)

    # weights per-check
    weights: Dict[str, float] = Field(default_factory=lambda: {
        "ml": 0.5,
        "velocity": 0.3,
        "sim_swap": 0.15,
        "night": 0.05,
    })

    decision_thresholds: DecisionThresholds = Field(default_factory=DecisionThresholds)

    config_version: str = Field("v1")

    @field_validator("weights")
    @classmethod
    def weights_sum_ok(cls, v):
        s = sum(v.values())
        if s <= 0:
            raise ValueError("weights must sum to > 0")
        return v

    @classmethod
    def from_store(cls, loader_callable) -> "FraudConfig":
        raw = loader_callable() or {}
        return cls(**raw)
"""Configurable thresholds and settings for fraud detection."""
from datetime import time

# Thresholds
DEFAULTS = {
    "velocity_window_seconds": 60,
    "velocity_txn_threshold": 10,
    "high_value_amount": 10000.0,  # currency units
    "night_start": time(0, 0),
    "night_end": time(5, 0),
    "ml_model_path": None,  # path to serialized model (joblib)
}
