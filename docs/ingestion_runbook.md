# Ingestion Runbook

This runbook documents the ingestion design, partitioning strategy, schema evolution policy, DLQ replay procedure, monitoring thresholds, and required tests for the M-Pesa real-time pipeline.

## Goals
- Ensure ordered per-customer processing (msisdn)
- Guarantee schema enforcement and safe handling of schema drift
- Provide replayable, auditable DLQ and raw data retention
- Surface consumer lag and backpressure early via alerts
- Provide testable procedures for exactly-once/idempotent processing verification

## Topic partitioning
- Topic: `mpesa-transactions` (raw)
- Partition key: `msisdn` (phone number) — use normalized E.164 string
- Rationale: per-customer ordering required for velocity, SIM-swap, and session-aware checks. With `msisdn` as key, all events for a customer land in same partition and processed by same consumer instance.
- Recommended partitions: start with `N=12` (or `#cores * 2`) and scale based on throughput/retention. Re-partitioning strategy requires rekeying if you change the key.

## Schema enforcement
- Use Confluent Schema Registry with Avro (or Protobuf) schemas for `mpesa-transactions` and `mpesa-fraud-alerts`.
- Producer-side: enforce `value.schema.id` at publish time; producers must fail to send if schema validation fails.
- Consumer-side: validate `message` against the schema before any stateful processing. If validation fails, write the raw message + validation error to DLQ topic `mpesa-transactions-dlq` (include headers: `schema_error`, `original_topic`, `partition`, `offset`).
- Backwards/forwards compatibility policy:
  - Additive optional fields: allowed (backwards compatible)
  - Removing fields: disallowed without migration
  - Changing types: requires schema evolution plan and pipeline upgrade window

## Dead Letter Queue (DLQ)
- DLQ topic: `mpesa-transactions-dlq` (compact=false, replication=3)
- Messages in DLQ must be durable and contain: raw payload, original metadata (topic/partition/offset/timestamp), schema error message, consumer id that wrote it.
- DLQ replay procedure:
  1. Inspect DLQ with a consumer script `scripts/inspect_dlq.py --topic mpesa-transactions-dlq --limit 100` to triage issues.
  2. Fix producer data or update schema if change is intended.
  3. To replay, use `scripts/replay_dlq.py --source-topic mpesa-transactions-dlq --target-topic mpesa-transactions --start-offset <o> --end-offset <o>` which will re-emit valid messages with original keys and headers.
  4. Track replay run id and mark time-range in a `replay_audit` table for reconciliation.

## Retention & Replay
- Configure Kafka retention for raw topic to support replays: at minimum 7 days; recommend 30 days for incident recovery.
- Additionally archive raw topic to S3 (parquet) via Kafka Connect (daily partitioned) for long-term reprocessing and audit.

## Exactly-once and idempotency
- At ingest producers: enable idempotent producer (Confluent) and assign transactional.id when batch publishing.
- Streaming engine: use Kafka transactions or a stream processing engine with checkpointing and exactly-once semantics (Flink with two-phase commit to sinks) to avoid double writes.
- Consumer design: make downstream writes idempotent (upserts or INSERT ... ON CONFLICT DO NOTHING) keyed by `transaction_id`.
- Verification test: simulate a consumer crash during commit, restart consumer and assert each transaction_id is stored only once in `mpesa_transactions_raw`.

## Backpressure & Late Data
- Use Flink watermarking and a bounded lateness policy (e.g., 5 minutes). Late events beyond window go to `mpesa-transactions-late` side-output for manual review or alternative processing.
- Configure the pipeline to surface buffer/queue sizes and apply backpressure to upstream Kafka consumers (via consumer pause/resume) rather than letting memory grow unbounded.

## Monitoring & Alerts
- Metrics to expose:
  - `mpesa_kafka_consumer_lag` (topic, partition) — alert if total lag > 100k messages or any partition lag > 10000 for more than 5 minutes
  - `mpesa_pipeline_health` (0/1) — derived from health checks
  - DLQ depth: `mpesa_dlq_depth` — alert if > 100 messages or increasing trend 3x over 15 minutes
  - Scoring latency: p50/p95/p99; alert if p95 > 1s (SLA)
  - Review queue size and oldest age — alert if oldest > 24 hours or queue > team capacity
- Suggested alert thresholds (tunable):
  - Consumer lag total > 100k -> Severity: P1
  - Partition lag > 10k for 5 minutes -> P1
  - DLQ depth > 100 -> P2
  - p95 scoring latency > 1s -> P2

## Tests and validation
- Unit tests:
  - Schema validation unit that rejects invalid payloads and routes to DLQ mock.
  - Idempotency unit for `insert_transaction` and `insert_fraud_alert` (using test DB) to ensure ON CONFLICT behavior.
- Integration tests (CI job with Kafka test cluster):
  - Partitioning test: produce two messages with same `msisdn` and assert both land in same partition key and processed in order.
  - Exactly-once simulation: produce N messages, kill consumer mid-batch, restart, assert no duplicates.
  - DLQ roundtrip: produce malformed messages, assert they appear in DLQ, run `replay_dlq.py` after fix, assert they re-enter main topic and are processed.
  - Backpressure test: apply artificial slowness to scoring function and assert consumer lag metric increases and alert would trigger.

## Runbook procedures
- How to triage consumer lag:
  - Check consumer group: `kafka-consumer-groups --bootstrap-server $BROKER --describe --group mpesa-consumer-group`
  - Inspect partition lags and which partitions are stuck.
  - Check dependent services (DB, Redis, model server) health and recent errors.
- How to run DLQ replay safely:
  - Test replay against staging cluster.
  - Use `--dry-run` mode on `replay_dlq.py` to validate transforms and keys.
  - Run replay in small batches and monitor consumer lag and error rates.

## Scripts (examples)
- `scripts/inspect_dlq.py` — list recent DLQ messages with metadata
- `scripts/replay_dlq.py` — replay DLQ to target topic with validation and rate-limit
- `scripts/consumer_restart_test.py` — automation for exactly-once restart test

## Ownership and cadence
- Consumer owner: `data-platform-team@company` (on-call rotation)
- Schema owner: `api-team@company` (changes must be coordinated)
- Replay audits: data-engineering team runs monthly replay drills

## Appendix: quick commands
```bash
# Check consumer groups
kafka-consumer-groups --bootstrap-server $KAFKA_BROKERS --describe --group mpesa-consumer-group

# Tail DLQ (small sample)
kafka-console-consumer --bootstrap-server $KAFKA_BROKERS --topic mpesa-transactions-dlq --from-beginning --max-messages 50

# Replay DLQ (dry-run)
# python scripts/replay_dlq.py --source-topic mpesa-transactions-dlq --target-topic mpesa-transactions --dry-run
```

---

This runbook is intended as the canonical ingestion reference. Next steps: implement schema validation in the consumer code paths, add CI integration tests that spin up Kafka (or use Testcontainers), and wire the monitoring alerts into Grafana/Prometheus.
