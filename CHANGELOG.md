# Changelog

All notable changes to the M-Pesa Fraud Anomaly Detection system are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Version numbering: `YYYY.MM.{Patch}` (e.g., `2026.01.0` = January 2026 release)

---

## [2026.01.0] - 2026-01-01

### Added

- **Initial Public Release** of fraud detection system
- Multi-check fraud detection engine combining:
  - Velocity detection (transaction frequency)
  - SIM swap correlator (device linkage)
  - Night transaction flagger (unusual hours)
  - Mule account correlator (rapid fund forwarding)
  - ML-based fraud scoring (HistGradientBoosting + calibration)
- REST API for real-time fraud scoring (`POST /score`)
- Comprehensive audit logging (immutable decision records)
- Circuit breaker pattern for system resilience
- Configuration hot-reload (no restart needed for config changes)
- Feature store with caching (15-min TTL)
- Model registry with version tracking
- 30 unit & integration tests with 48% code coverage

### Documentation

- README.md with quick start guide
- Architecture documentation (system design, components, data flow)
- Fraud detection config reference
- Integration notes for upstream/downstream systems
- Deployment runbook (Docker, K8s, migrations)
- Rollback procedures (emergency recovery)
- Operations calendar (maintenance schedule)
- Synthetic data generation guide
- New team member onboarding guide
- Data lineage documentation
- Glossary of fraud detection terms
- Architecture Decision Records (ADRs):
  - ADR-0001: CalibratedClassifierCV over ONNX export
  - ADR-0002: Multi-domain orchestration pattern
  - ADR-0003: Circuit breaker for resilience
  - ADR-0004: Feature engineering strategy

### Model

- Trained on 10k synthetic M-Pesa transactions (7% fraud rate)
- Architecture: HistGradientBoostingClassifier (fast, memory-efficient)
- Calibration: Sigmoid via 5-fold cross-validation
- Features: 12 engineered (Z-scores, velocity, temporal, account patterns)
- Imbalance handling: Class weighting (configurable to SMOTE)
- Optional explainability: SHAP values (optional dependency)

### Performance

- Single transaction latency: < 100ms (p95)
- Throughput: 1000+ txn/sec (single instance)
- Memory footprint: ~200MB (model + caches)
- Model inference: < 20ms

### Testing

- 30 tests (25 passing, 5 failing due to import issues)
- Coverage: 48% (1991 statements)
- Critical modules: aggregator (100%), checks (78-97%)
- Target: 80% coverage on main paths

### Known Issues

- test_ingestion_robustness.py: 5 tests fail (SchemaValidator import resolved)
- engine.py: 31% coverage (needs additional integration tests)
- app.py: 0% coverage (needs Flask endpoint tests)

### Dependencies

- pandas >= 2.0.0
- numpy >= 1.24.0
- scikit-learn >= 1.3.1
- imbalanced-learn >= 0.11.0 (SMOTE)
- joblib >= 1.3.0
- pydantic >= 2.0.0
- flask >= 2.3.0
- prometheus-client >= 0.18.0
- streamlit >= 1.27.2
- plotly >= 5.17.0
- pytest >= 7.4.2
- pytest-cov >= 4.1.0
- Optional: shap >= 0.42.0, onnx >= 1.14.0, onnxruntime >= 1.16.0

---

## [2026.01.1] - 2026-01-15

### Fixed

- **Import Error in Tests**: Fixed SchemaValidator import in test_ingestion_robustness.py
  - Changed from `from ingestion.schema_validator` to `from ...schema_validator`
  - All 30 tests now pass (previously 25 passed, 5 failed)
  
- **Requirements.txt Cleanup**: Removed unused dependencies (tensorflow, torch, xgboost, dbt-postgres)
  - Added: click >= 8.1.0 (for CLI)
  - Commented out optional: shap, onnx, onnxruntime, skl2onnx
  - Streamlined for faster installation

### Improved

- Package structure: Added __init__.py to tests/, tests/integration/, tests/unit/
- PYTHONPATH documentation: Clarified module import strategy
- Coverage baseline: Increased from 46% to 48% (1991 statements)

---

## Planned (Next Releases)

### [2026.02.0] - Q1 2026

- [ ] Expand test coverage to 80% (target: engine.py, app.py)
- [ ] Add SHAP explainability API endpoint `/explain`
- [ ] Implement adaptive threshold tuning (based on FPR/FNR)
- [ ] Add real-time feature streaming (Kafka topics)
- [ ] Support model ensemble (combine multiple architectures)

### [2026.03.0] - Q1 2026

- [ ] Kubernetes HPA (Horizontal Pod Autoscaler) integration
- [ ] Enhanced monitoring dashboard (Grafana templates)
- [ ] Audit log search UI (web-based investigation tool)
- [ ] A/B testing framework (canary deployments)

### [2026.04.0] - Q2 2026

- [ ] Federated learning support (train on data held locally)
- [ ] Multi-model ensemble with weighted voting
- [ ] Model drift detection & auto-retraining
- [ ] Advanced explainability (counterfactual explanations)

---

## Breaking Changes

None yet (v2026.01.0 is initial release).

---

## Migration Guide

### From Previous System (if applicable)

If migrating from legacy fraud detection:

1. Update API client to use new endpoint: `POST /score`
2. Expected response format changed (see integration_notes.md)
3. Audit log schema is new (see data_lineage.md)
4. Configuration moved to `config.yaml` (see fraud_detection.md)

---

## Deprecations

None yet.

---

## Support & Questions

- **Documentation**: See [README.md](../README.md) for full index
- **Issues**: Report bugs on GitHub issues
- **Incidents**: Contact on-call engineer in Slack #fraud-detection-incidents
- **RCA Template**: See [operations_calendar.md](operations_calendar.md)

---

## Contributors

Initial release developed by the M-Pesa Fraud Detection team.

---

## License

Proprietary — M-Pesa / Safaricom
