# ADR-0002: Multi-Domain Fraud Detection via Orchestration

**Date**: 2026-01-01  
**Status**: Accepted  
**Context**: Fraud detection must integrate with multiple payment domains (M-Pesa, Equitel, Equity Bank, etc.) and unified risk assessment  
**Decision**: Implement multi-domain orchestration pattern where domain-specific engines (like fraud_anomaly_detection) are composed into a single unified engine.

## Problem

Fraud detection requirements span multiple payment domains:
- **M-Pesa**: Mobile money, velocity-based fraud dominant
- **Equitel**: Telecom-based payments, SIM-linked risks
- **Equity Bank**: Card/account-based, different fraud patterns
- **KRA Tax**: Government payments, data leakage risks

Each domain has unique:
- Check types (M-Pesa: velocity; Equity: CVV entry, card cloning)
- Thresholds (M-Pesa: 10 txn/24h; Equity: 3 cards/24h)
- Audit requirements (regulatory differences)

**Naive Approach**: Single monolithic engine with all domain logic
- **Problem**: 100+ configuration flags, hard to reason about
- **Risk**: Change in M-Pesa checks accidentally breaks Equitel logic

## Solution

Implement **Domain Segregation + Unified Orchestration**:

```
Transaction
    ↓
[Route by Domain] (mpesa, equitel, equity_bank, kra)
    ↓
[Domain-Specific Engine]
    ├─ fraud_anomaly_detection (M-Pesa)
    ├─ equitel_fraud (Equitel)
    ├─ equity_bank_fraud (Equity)
    └─ kra_tax_fraud (KRA)
    ↓
[Unified Orchestrator] (fraud_detection_unified)
    ├─ Combine domain scores
    ├─ Apply cross-domain rules
    ├─ Handle multi-domain risk (same user in multiple domains)
    └─ Global audit log
    ↓
Decision: ACCEPT | REVIEW | BLOCK
```

**Architecture**:

```python
# fraud_detection_unified/engine.py
class ConsolidatedFraudDetectionEngine:
    def __init__(self):
        self.mpesa_engine = MobileMoneyFraudEngine()
        self.equitel_engine = EquitelFraudEngine()
        self.equity_engine = EquityBankFraudEngine()
    
    def score_multi_domain(self, domain: str, txn: Dict) -> Decision:
        # Route to domain engine
        domain_decision = self._route_to_domain_engine(domain, txn)
        
        # Check for cross-domain patterns (e.g., same user in M-Pesa & Equitel)
        cross_domain_score = self._check_cross_domain_patterns(txn)
        
        # Combine and return
        return self._aggregate_decisions(domain_decision, cross_domain_score)
```

**Advantages**:
- ✅ Each domain is independent (changes don't bleed)
- ✅ Domain-specific thresholds & checks
- ✅ Reusable: M-Pesa engine can be deployed standalone or via unified
- ✅ Testability: Test each domain in isolation + unified integration

**Trade-offs**:
- ❌ More complex architecture (N engines + orchestrator)
- ❌ Operational overhead (deploy/monitor multiple services)
- ❌ Network latency: Unified engine calls domain engines (vs. monolithic single call)

## Design Patterns

### 1. Dependency Injection
Each domain engine is injected into unified engine:

```python
class ConsolidatedFraudDetectionEngine:
    def __init__(self, 
                 mpesa_engine: FraudEngine = None,
                 equitel_engine: FraudEngine = None,
                 ...):
        self.mpesa_engine = mpesa_engine or MobileMoneyFraudEngine()
```

Allows testing with mock engines.

### 2. Configuration Inheritance
Domain-specific config extends base config:

```python
# Base config
class FraudConfig:
    ml_weight: float = 0.7
    velocity_threshold: int = 10

# M-Pesa specific
class MPesaFraudConfig(FraudConfig):
    velocity_threshold: int = 10  # Override if different
    sim_swap_enabled: bool = True
```

### 3. Decision Aggregation
Combine domain scores via weighted averaging:

```python
def aggregate(self, decisions: Dict[str, Decision]) -> Decision:
    mpesa_score = decisions["mpesa"].risk_score
    equitel_score = decisions["equitel"].risk_score
    
    # Weighted by volume/importance
    combined = (mpesa_score * 0.5) + (equitel_score * 0.5)
    return self._to_decision(combined)
```

## Deployment Strategy

### Option 1: Separate Services (Recommended)
```
fraud_anomaly_detection (M-Pesa):  :5001/score
equitel_fraud:                      :5002/score
equity_bank_fraud:                  :5003/score
fraud_detection_unified:            :5000/score_multi_domain (calls above)
```

**Benefit**: Independent scaling, deployment, monitoring

### Option 2: Monolithic with Internal Routing
All domains in one service, internal routing:
```
fraud_detection_unified:            :5000/score?domain=mpesa
```

**Benefit**: Simpler deployment, shared infrastructure

## Cross-Domain Risk Patterns

Example: **Same user in multiple domains with concurrent fraud**

```
M-Pesa:     User A has 5 txn/24h (normal)
Equitel:    User A has 2 txn/24h (normal)
Equity:     User A has 1 txn/24h (normal)

Individual domain engines: All ACCEPT

Unified engine detection:
- Same user across 3 domains in 1 hour → Unusual
- Possible: Account takeover (attacker using all accounts)
- Decision: Escalate to REVIEW (cross-domain anomaly)
```

## Alternatives Considered

### Alternative 1: Monolithic Single Engine
- **Rejected**: Hard to maintain, test independently, configure per-domain
- **Risk**: Changes in one domain break others

### Alternative 2: Separate API Layers (No Orchestration)
- **Rejected**: Upstream system must know all domains, call multiple endpoints
- **Risk**: Client complexity, missing cross-domain patterns

## Consequences

1. **Operational Complexity**: More services to deploy/monitor
   - Mitigation: Containerize, use Kubernetes for orchestration
   
2. **Latency**: Unified engine calls multiple domain engines
   - Mitigation: Parallel calls via async/threading, optimize network
   - Typical: 20ms per domain engine, 5-10ms orchestration = ~35ms total (acceptable)

3. **Shared State**: Cross-domain pattern detection needs global audit log
   - Mitigation: Central database table with indexes on user ID + timestamp

## Implementation

- [fraud_detection_unified/engine.py](../../fraud_detection_unified/engine.py): Unified orchestrator
- [__init__.py](../../fraud_anomaly_detection/__init__.py): M-Pesa domain engine exports
- Tests: [tests/integration/test_integration_engine.py](../../tests/integration/test_integration_engine.py)

## Future Enhancements

1. **Async Multi-Domain Scoring**: Parallel calls to domain engines
2. **Dynamic Domain Registration**: Plugin architecture for new domains
3. **Global Fraud Ring Detection**: Link users across domains (money laundering)
4. **A/B Testing**: Test domain thresholds independently in prod

## References

- Martin Fowler: Microservices Architecture
- Event-driven orchestration pattern
- Service Mesh (Istio, Linkerd) for inter-service communication

## Approval

- **Architect**: Carol (carol@company.com) - Approved
- **Platform Lead**: David (david@company.com) - Approved
- **Date**: 2026-01-01
