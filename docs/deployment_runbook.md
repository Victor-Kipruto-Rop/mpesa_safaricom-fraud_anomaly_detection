# Deployment Runbook

## Prerequisites

- Docker & Docker Compose installed
- Kubernetes cluster (if using K8s) with kubectl configured
- PostgreSQL 13+ running and accessible
- Environment variables configured (see `.env.example`)

## Local Development Deployment

### 1. Environment Setup

```bash
cd mpesa_safaricom/fraud_anomaly_detection

# Create .env from template
cp .env.example .env

# Edit .env with your database credentials
export DATABASE_URL="postgresql://user:password@localhost:5432/fraud_detection"
export FLASK_ENV=development
```

### 2. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### 3. Initialize Database

```bash
# Run migrations (if using Alembic)
alembic upgrade head

# Or manually create tables
psql -U postgres -d fraud_detection < schema.sql
```

### 4. Train/Load Model

```bash
# Train a new model
python ml/train_model.py \
  --data ml/synthetic_transactions.parquet \
  --output-dir models/run_$(date +%Y-%m-%d_%H) \
  --imbalance-method balanced

# Or use existing model
# (Model loading is automatic from serving/model_registry.py)
```

### 5. Start Flask App

```bash
python -m flask run --host=0.0.0.0 --port=5000
```

App is now live at `http://localhost:5000`.

## Docker Deployment

### Build Image

```bash
docker build -f Dockerfile -t fraud-detection:latest .
```

### Run Container

```bash
docker run -d \
  --name fraud-detection \
  -p 5000:5000 \
  -e DATABASE_URL="postgresql://user:password@db:5432/fraud_detection" \
  -e FLASK_ENV=production \
  fraud-detection:latest
```

### Docker Compose (Multi-Service)

```bash
docker-compose up -d
```

**Services** (defined in `docker-compose.yml`):
- `db`: PostgreSQL 15
- `fraud-api`: Flask app
- `redis` (optional): Feature caching

## Kubernetes Deployment

### Prerequisites

```bash
# Ensure you have kubectl configured for target cluster
kubectl config current-context
```

### 1. Create Namespace

```bash
kubectl create namespace fraud-detection
```

### 2. Create Secrets

```bash
kubectl create secret generic fraud-detection-secrets \
  --from-literal=database-url="postgresql://..." \
  --from-literal=flask-secret="..." \
  -n fraud-detection
```

### 3. Deploy Application

```bash
kubectl apply -f k8s/deployment.yaml -n fraud-detection
kubectl apply -f k8s/service.yaml -n fraud-detection
```

### 4. Verify Deployment

```bash
kubectl get pods -n fraud-detection
kubectl logs -f deployment/fraud-detection-api -n fraud-detection
```

### 5. Expose Service

```bash
# Port forward (local testing)
kubectl port-forward svc/fraud-detection-api 5000:5000 -n fraud-detection

# Or configure ingress
kubectl apply -f k8s/ingress.yaml -n fraud-detection
```

## Health Checks

### Manual

```bash
curl http://localhost:5000/health
# Expected: {"status": "healthy"}
```

### Kubernetes Readiness Probe

Configured in `k8s/deployment.yaml`:

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 5000
  initialDelaySeconds: 10
  periodSeconds: 5
```

## Database Migrations

### Using Alembic

```bash
# Generate new migration
alembic revision --autogenerate -m "Add fraud_audit_logs table"

# Apply migration
alembic upgrade head

# Rollback (one version)
alembic downgrade -1
```

## Model Deployment

### Update Model in Production

```bash
# Train new model locally
python ml/train_model.py --output-dir models/run_prod

# Copy model artifact to production
scp models/run_prod/mobile_money_fraud_calibrated.joblib \
  prod-server:/opt/fraud-detection/models/

# Update config to point to new model
kubectl set env deployment/fraud-detection-api \
  MODEL_PATH=/opt/fraud-detection/models/mobile_money_fraud_calibrated.joblib \
  -n fraud-detection

# Model will be reloaded on next transaction
```

### Fallback to Previous Model

```bash
# Revert MODEL_PATH in config
kubectl set env deployment/fraud-detection-api \
  MODEL_PATH=/opt/fraud-detection/models/previous_model.joblib \
  -n fraud-detection

# No service restart needed (hot-loaded via ModelRegistry)
```

## Scaling

### Horizontal Scaling (K8s)

```bash
# Scale to 3 replicas
kubectl scale deployment fraud-detection-api \
  --replicas=3 \
  -n fraud-detection

# Or use HPA (Horizontal Pod Autoscaler)
kubectl apply -f k8s/hpa.yaml -n fraud-detection
```

### Load Balancing

In K8s, traffic is automatically distributed across replicas via Service.

For on-prem, use Nginx/HAProxy with round-robin:

```nginx
upstream fraud_detection {
    server 10.0.0.1:5000;
    server 10.0.0.2:5000;
    server 10.0.0.3:5000;
}

server {
    listen 443 ssl;
    location /fraud {
        proxy_pass http://fraud_detection;
    }
}
```

## Monitoring Post-Deployment

### Prometheus Metrics

```bash
curl http://localhost:5000/metrics
```

Import into Prometheus scrape config:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'fraud-detection'
    static_configs:
      - targets: ['localhost:5000']
```

### Log Aggregation

Forward logs to ELK/Splunk:

```bash
# JSON logs on stdout
docker logs fraud-detection | jq .
```

## Troubleshooting

### App Not Starting

```bash
# Check logs
kubectl logs -f deployment/fraud-detection-api -n fraud-detection

# Common issues:
# - DATABASE_URL not set
# - Model file not found
# - Port already in use
```

### Database Connection Errors

```bash
# Test connection string
psql "$DATABASE_URL" -c "SELECT 1"

# Check credentials in .env
grep DATABASE_URL .env
```

### High Latency

```bash
# Check slow queries
kubectl exec -it pod/fraud-detection-api -- \
  python -c "import logging; logging.basicConfig(level=logging.DEBUG)"

# Profile with cProfile
python -m cProfile -s cumtime ml/train_model.py --data ...
```

## Post-Deployment Checklist

- [ ] `/health` endpoint returns 200
- [ ] `/metrics` shows transaction counts > 0
- [ ] Database table counts > 0 (audit logs being written)
- [ ] No error logs in stderr
- [ ] Model inference latency < 100ms (check metrics)
- [ ] Replica count matches expected (K8s)
- [ ] Backup of database has run
- [ ] Monitoring dashboards loading data

## Rollback (See Also: [rollback_procedures.md](rollback_procedures.md))

If deployment is broken:

```bash
# Immediately scale down bad deployment
kubectl scale deployment fraud-detection-api --replicas=0 -n fraud-detection

# Revert to previous image
kubectl set image deployment/fraud-detection-api \
  fraud-detection=fraud-detection:previous-stable \
  -n fraud-detection

# Scale back up
kubectl scale deployment fraud-detection-api --replicas=3 -n fraud-detection

# Verify
kubectl get pods -n fraud-detection
```
