# Rollback Procedures

## Emergency Rollback (< 5 minutes)

### Situation: Broken Model or Bad Deployment

**Symptoms:**
- 50%+ error rate on `/score` endpoint
- Mean latency > 500ms
- ML model crashes on inference
- High false positive rate (blocking legitimate transactions)

**Immediate Action:**

```bash
# OPTION 1: Revert to Previous Image (K8s)
kubectl rollout undo deployment/fraud-detection-api -n fraud-detection

# Verify the rollback
kubectl rollout status deployment/fraud-detection-api -n fraud-detection

# Check pods are running
kubectl get pods -n fraud-detection | head -10
```

**OPTION 2: Switch Model (Fast, No Restart)**

```bash
# Update config to use fallback model
kubectl set env deployment/fraud-detection-api \
  MODEL_PATH=/opt/fraud-detection/models/fallback_model.joblib \
  -n fraud-detection

# No pod restart needed (hot-loaded via ModelRegistry)
# Transactions will use old model immediately
```

**OPTION 3: Disable ML, Use Rules Only**

```bash
# Set ML weight to 0
kubectl set env deployment/fraud-detection-api \
  ML_WEIGHT=0.0 \
  RULE_WEIGHT=1.0 \
  -n fraud-detection

# System falls back to velocity + SIM swap + night hours detection
```

**Verification:**

```bash
# Test endpoint manually
curl -X POST http://localhost:5000/score \
  -H "Content-Type: application/json" \
  -d '{"TransID":"TEST","MSISDN":"254712345678","TransAmount":"100","TransTime":"20260101120000"}'

# Expected: < 200ms response with valid decision

# Check error rate (Prometheus)
curl http://localhost:5000/metrics | grep fraud_detection_errors
```

---

## Database Rollback (if corrupted)

**Symptoms:**
- Duplicate audit logs
- Incorrect historical decisions
- Database query errors

### Step 1: Identify Last Good Backup

```bash
# List available backups
ls -lah /backups/fraud_detection/

# Verify backup integrity
pg_restore -t fraud_transaction_scores /backups/fraud_detection/backup_2026-01-01.sql
```

### Step 2: Restore from Backup

```bash
# CRITICAL: Ensure API is paused first
kubectl scale deployment fraud-detection-api --replicas=0 -n fraud-detection

# Wait for pods to shut down
sleep 10

# Restore database
pg_restore -d fraud_detection \
  -h localhost \
  -U postgres \
  /backups/fraud_detection/backup_2026-01-01.sql

# Verify tables exist
psql -U postgres -d fraud_detection -c "\dt"

# Resume API
kubectl scale deployment fraud-detection-api --replicas=3 -n fraud-detection
```

---

## Configuration Rollback

**If Bad Config Deployed:**

```bash
# Revert ConfigMap
kubectl rollout undo configmap fraud-detection-config -n fraud-detection

# Or manually restore from git
git checkout main -- config.yaml
kubectl apply -f config.yaml -n fraud-detection

# Verify pods pick up new config (30s hot-reload window)
sleep 35
kubectl logs deployment/fraud-detection-api -n fraud-detection | grep "Config reloaded"
```

---

## Gradual Rollback (Canary)

**If you want to test before full rollback:**

```bash
# 1. Create new canary deployment with old version
kubectl set image deployment/fraud-detection-canary \
  fraud-detection=fraud-detection:previous-stable \
  -n fraud-detection

# 2. Send 10% of traffic to canary
kubectl patch service fraud-detection-api -n fraud-detection \
  -p '{"spec":{"selector":{"version":"canary"}}}'

# 3. Monitor metrics for 1 hour
watch 'curl http://localhost:5000/metrics | grep fraud_detection'

# 4. If good, promote canary to main
kubectl patch service fraud-detection-api -n fraud-detection \
  -p '{"spec":{"selector":{"version":"stable"}}}'

# 5. Shut down old deployment
kubectl delete deployment fraud-detection-api -n fraud-detection
kubectl rename deployment fraud-detection-canary fraud-detection-api -n fraud-detection
```

---

## Partial Rollback (Specific Feature)

**If only one check is broken (e.g., ML model):**

```bash
# Disable just the problematic check
kubectl set env deployment/fraud-detection-api \
  ML_SCORER_ENABLED=false \
  -n fraud-detection

# System continues with velocity + SIM swap + night hours
# Can roll out ML fix independently later

# To re-enable
kubectl set env deployment/fraud-detection-api \
  ML_SCORER_ENABLED=true \
  -n fraud-detection
```

---

## Post-Rollback Validation

### Run Automated Tests

```bash
# Ensure test data is still clean
kubectl exec -it deployment/fraud-detection-api -n fraud-detection -- \
  python -m pytest tests/ -v --tb=short

# Expected: All tests pass
```

### Check Key Metrics

```bash
# Use Prometheus to verify:
# 1. Error rate back to normal (< 1%)
# 2. Latency < 100ms (p95)
# 3. Decision distribution (% ACCEPT/BLOCK/REVIEW) matches historical pattern

# Query Prometheus
curl 'http://prometheus:9090/api/v1/query?query=fraud_detection_errors{job="fraud-detection"}'
```

### Manual Transaction Tests

```bash
# Test legitimate transaction
curl -X POST http://localhost:5000/score \
  -H "Content-Type: application/json" \
  -d '{
    "TransID":"TEST_LEG_001",
    "MSISDN":"254712345678",
    "TransAmount":"1000",
    "TransTime":"20260101150000"
  }'
# Expected: ACCEPT or REVIEW (not BLOCK)

# Test high-risk transaction
curl -X POST http://localhost:5000/score \
  -H "Content-Type: application/json" \
  -d '{
    "TransID":"TEST_RISK_001",
    "MSISDN":"254712345678",
    "TransAmount":"500000",
    "TransTime":"20260101030000"
  }'
# Expected: BLOCK or REVIEW
```

---

## Communication & Incident Log

After any rollback, **immediately**:

1. **Notify stakeholders** (fraud ops, business team)

```
🚨 INCIDENT ROLLBACK

Timestamp: 2026-01-01T12:00:00Z
Reason: Model inference latency spike
Action: Reverted to previous model version
Status: Ongoing investigation
Next Update: 12:30 UTC
```

2. **Document in incident log** (Slack/JIRA/incident tracking)

```
Title: Model v2.0 Rollback - High Latency
Start: 2026-01-01T11:50Z
Resolution: 2026-01-01T12:05Z (15 min)
RCA: SHAP computation not cached, added exponential backoff in v2.1
```

3. **Schedule RCA** (Root Cause Analysis meeting within 24h)

---

## Prevention: Pre-Deployment Validation

To avoid needing rollbacks:

1. **Always run tests first**:
   ```bash
   pytest tests/ --cov -v
   ```

2. **Canary deploy to staging**:
   ```bash
   kubectl apply -f k8s/staging.yaml
   # Run integration tests against staging for 1h
   ```

3. **Monitor metrics before full prod deploy**:
   ```bash
   # Compare staging metrics to prod baseline
   ```

4. **Use feature flags** for gradual rollout:
   ```python
   if config.ml_v2_enabled:
       use_new_model()
   else:
       use_stable_model()
   ```

---

## Rollback Decision Tree

```
┌─ Is /health endpoint responsive?
│  ├─ YES → Might be recoverable without rollback
│  │        • Check logs for specific errors
│  │        • Try config rollback first
│  └─ NO → Immediate image rollback required
│
┌─ Is error rate > 10%?
│  ├─ YES → Roll back immediately (Steps above)
│  └─ NO → Investigate further, monitor closely
│
┌─ Is this a model issue?
│  ├─ YES → Switch to fallback model (no restart needed)
│  └─ NO → Full deployment rollback or config rollback
```

---

## Support & Escalation

- **On-Call Fraud Eng**: [contact]
- **Database Admin**: [contact]
- **ML Engineer**: [contact]
- **Incident Slack Channel**: #fraud-detection-incidents
