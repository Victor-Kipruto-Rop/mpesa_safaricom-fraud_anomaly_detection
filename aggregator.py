from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
from enum import Enum


class Decision(Enum):
    ALLOW = "ALLOW"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


@dataclass
class FraudScoreResult:
    score: float
    decision: Decision
    explanation: Dict[str, Any]


class FraudScoreAggregator:
    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        # config can contain thresholds and interaction boosts
        self.config = config or {}
        self.thresholds = self.config.get("thresholds", {"block": 0.9, "review": 0.6})
        # interactions: tuple of names -> boost weight
        self.interactions: Dict[Tuple[str, ...], float] = self.config.get("interactions", {("ml_scorer", "sim_swap"): 0.15})

    def aggregate(self, check_results: List[Any]) -> FraudScoreResult:
        # base weighted sum
        score = 0.0
        explanation = {"checks": [], "interaction_boosts": []}
        name_to_result = {}
        for r in check_results:
            score += r.score * r.weight
            name_to_result[r.name] = r
            if r.triggered:
                explanation["checks"].append({"name": r.name, "reason": r.reason, "score": r.score, "weight": r.weight})

        # interaction layer: for each configured interaction, if all present and triggered, add boost
        interaction_total = 0.0
        for names, boost in self.interactions.items():
            if all((n in name_to_result and name_to_result[n].triggered) for n in names):
                interaction_total += boost
                explanation["interaction_boosts"].append({"names": names, "boost": boost})

        final_score = min(1.0, max(0.0, score + interaction_total))

        # decision thresholds
        decision = Decision.ALLOW
        if final_score >= self.thresholds.get("block", 0.9):
            decision = Decision.BLOCK
        elif final_score >= self.thresholds.get("review", 0.6):
            decision = Decision.REVIEW

        explanation["base_score"] = score
        explanation["interaction_total"] = interaction_total
        explanation["final_score"] = final_score
        return FraudScoreResult(score=final_score, decision=decision, explanation=explanation)
 
