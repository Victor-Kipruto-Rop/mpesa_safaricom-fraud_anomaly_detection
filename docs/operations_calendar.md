# Operations Calendar

## Recurring Maintenance Windows

### Weekly (Every Monday, 02:00-04:00 UTC)

**Database Maintenance**
- Vacuum & analyze main tables
- Index fragmentation check
- Connection pool reset

**Command:**
```bash
./scripts/weekly_db_maintenance.sh
```

### Monthly (1st of month, 22:00-00:00 UTC)

**Model Retraining**
- Retrain classifier on latest month's data
- Evaluate on holdout set
- Prepare for production deployment

**Steps:**
```bash
python ml/train_model.py \
  --data ml/monthly_transactions.parquet \
  --output-dir models/run_$(date +%Y-%m) \
  --sample-size 200

# Evaluate
python ml/evaluate_model.py models/run_$(date +%Y-%m)/mobile_money_fraud_calibrated.joblib

# Approve before deploying to prod
# See deployment_runbook.md
```

### Quarterly (Q1: Jan 1, Q2: Apr 1, Q3: Jul 1, Q4: Oct 1, 18:00 UTC)

**Full System Review**
- Coverage audit (test coverage report)
- Config baseline audit
- Performance SLA review
- Security scan (dependencies, secrets)

**Checklist:**
- [ ] Run `pytest --cov` and compare to baseline (target: 80%+)
- [ ] Review config schema for unused settings
- [ ] Check P50/P95 latency trends (target: < 100ms / < 200ms)
- [ ] Run `pip audit` for CVE detection

### Annual (January 15, 10:00 UTC)

**Architecture Review**
- ADR review (see docs/adr/)
- Dependency version bump
- Performance regression testing
- Disaster recovery drill

---

## Key Dates & Blackout Periods

| Date | Event | Impact | Action |
|------|-------|--------|--------|
| Dec 20-31 | Holiday Break | Reduced staffing | No deployments, critical fixes only |
| Apr 1-15 | Financial Year-End | High transaction volume | Monitor closely, scale as needed |
| Jul 15-20 | MNO Upgrade Window | Potential transaction delays | Expect latency spikes |

---

## On-Call Schedule

```
Week of Jan 1-7:   Alice (alice@company.com)
Week of Jan 8-14:  Bob (bob@company.com)
Week of Jan 15-21: Carol (carol@company.com)
Week of Jan 22-28: David (david@company.com)
... (rotating weekly)
```

**On-Call Responsibilities:**
- Monitor `/health` endpoint (15-min SLA for alerts)
- Respond to production incidents (see rollback_procedures.md)
- Escalate to team lead if unable to resolve in 30 min

---

## Monitoring Dashboard Refresh

**Daily**: 10:00 UTC
- Review overnight error logs
- Check decision distribution (% ACCEPT/BLOCK/REVIEW)
- Verify model latency < 100ms

**Weekly**: Every Friday, 15:00 UTC
- Full metrics review with team
- Trend analysis (FPR, FNR, precision)
- Plan interventions if needed

---

## Config Update Schedule

**Monthly**: Every 2nd Tuesday at 14:00 UTC

Review & approve config changes:
- `velocity_threshold`: Based on transaction volume trends
- `ml_weight`: Adjust if FPR/FNR needs rebalancing
- `circuit_breaker_threshold`: Tune based on incident frequency

**Process:**
1. Create PR with proposed changes
2. A/B test on canary (10% traffic)
3. Get approval from fraud ops team
4. Merge & hot-reload (no restart)

---

## Release Calendar

**Version Numbering**: YYYY.MM.{Patch}
- **2026.01.0**: January release
- **2026.01.1**: Patch release (bug fix within same month)

**Release Cadence**: 1st of each month (typically)

**Release Steps**:
1. Create release branch `release/2026-01`
2. Run full test suite
3. Create git tag `v2026.01.0`
4. Build Docker image
5. Deploy to staging → prod
6. Document in CHANGELOG.md

---

## Backup Schedule

| Backup Type | Frequency | Retention | Location |
|-------------|-----------|-----------|----------|
| Database (full) | Daily @ 23:00 UTC | 30 days | `/backups/fraud_detection/` |
| Database (incremental) | Every 6 hours | 7 days | `/backups/fraud_detection/inc/` |
| Config (git) | Real-time | Infinite | GitHub repo |
| Model artifacts | On deploy | Last 3 versions | `/models/archive/` |

**Backup Verification**: Weekly (every Thursday @ 09:00 UTC)

```bash
./scripts/verify_backups.sh
# Checks: file integrity, restore test, encryption status
```

---

## Incident Post-Mortems

**Schedule**: Every 2 weeks, Friday @ 15:00 UTC (if incidents occurred)

**Format**: Slack thread in #fraud-detection-incidents

**Template**:
```
🔍 POST-MORTEM: [Incident Title]

Timeline:
- 2026-01-01T12:00Z: Incident started (error rate spike)
- 2026-01-01T12:15Z: Detected via alert
- 2026-01-01T12:20Z: Rollback initiated
- 2026-01-01T12:25Z: Service recovered

Root Cause:
- [Technical reason]

Impact:
- Duration: 25 minutes
- Transactions affected: ~5000 (0.1%)
- Decision accuracy: 98.2% (normal: 99.1%)

Action Items:
- [ ] @alice Fix in v2026.02
- [ ] @bob Add monitoring for metric X
- [ ] @carol Update runbook

Lessons Learned:
- ...
```

---

## SLA Targets & Review

**Service Level Agreement (SLA)**:

| Metric | Target | Check Frequency |
|--------|--------|-----------------|
| Uptime | 99.5% | Daily |
| P95 Latency | < 200ms | Daily |
| Decision Accuracy | > 99% | Weekly |
| Error Rate | < 1% | Real-time alert |

**Review**: 1st Friday of each month @ 14:00 UTC

---

## Contact Information

| Role | Name | Email | Phone | On-Call? |
|------|------|-------|-------|----------|
| Team Lead | Alice | alice@company.com | +1-555-0001 | Weekdays |
| ML Engineer | Bob | bob@company.com | +1-555-0002 | Weekly |
| Platform Engineer | Carol | carol@company.com | +1-555-0003 | Weekly |
| Database Admin | David | david@company.com | +1-555-0004 | As-needed |

**On-Call Escalation** (if primary doesn't respond in 15 min):
1. Text on-call engineer
2. Call team lead
3. Page dev manager

---

## Emergency Contacts

- **Fraud Operations Director**: fraud-ops@company.com
- **Chief Risk Officer**: cro@company.com
- **24/7 Incident Hotline**: +1-555-FRAUD-911
- **Slack**: #fraud-detection-incidents (monitored 24/7)
