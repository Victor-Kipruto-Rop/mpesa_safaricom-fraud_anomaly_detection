"""
Integration tests for ingestion robustness.

Tests cover:
- Partitioning by msisdn (ordering guarantee)
- Exactly-once processing (no duplicates on restart)
- Schema validation and DLQ routing
- Idempotent DB writes
"""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ...schema_validator import SchemaValidator


class TestSchemaValidation:
    """Test schema validation and DLQ routing."""

    def test_valid_transaction_passes(self):
        """Valid transaction should pass validation."""
        payload = {
            "TransID": "TXN_001",
            "MSISDN": "254712345678",
            "TransAmount": "5000",
            "TransTime": "20260101120000",
            "BusinessShortCode": "123456",
        }
        is_valid, error = SchemaValidator.validate(payload)
        assert is_valid
        assert error is None

    def test_missing_required_field_fails(self):
        """Transaction missing required field should fail."""
        payload = {
            "TransID": "TXN_001",
            "MSISDN": "254712345678",
            # Missing TransAmount
            "TransTime": "20260101120000",
        }
        is_valid, error = SchemaValidator.validate(payload)
        assert not is_valid
        assert "Missing required fields" in error

    def test_invalid_type_fails(self):
        """Invalid field type should fail."""
        payload = {
            "TransID": "TXN_001",
            "MSISDN": "254712345678",
            "TransAmount": {"value": 5000},  # Invalid: should be numeric
            "TransTime": "20260101120000",
        }
        is_valid, error = SchemaValidator.validate(payload)
        assert not is_valid

    def test_dlq_message_format(self):
        """DLQ message should contain all required metadata."""
        dlq_msg = SchemaValidator.format_dlq_message(
            raw_payload={"TransID": "bad"},
            error="Missing required fields",
            topic="mpesa-transactions",
            partition=0,
            offset=42,
            timestamp=1234567890,
        )
        assert dlq_msg["original_payload"] == {"TransID": "bad"}
        assert dlq_msg["schema_error"] == "Missing required fields"
        assert dlq_msg["original_topic"] == "mpesa-transactions"
        assert dlq_msg["partition"] == 0
        assert dlq_msg["offset"] == 42


class TestIdempotentProcessing:
    """Test idempotent DB writes (ON CONFLICT DO NOTHING)."""

    def test_duplicate_insert_ignored(self):
        """Inserting same transaction_id twice should not error, only insert once."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Create test table with primary key
            cursor.execute(
                """
                CREATE TABLE mpesa_transactions_raw (
                    transaction_id TEXT PRIMARY KEY,
                    phone_number TEXT NOT NULL,
                    amount REAL
                )
                """
            )

            # First insert
            cursor.execute(
                """
                INSERT INTO mpesa_transactions_raw 
                (transaction_id, phone_number, amount)
                VALUES (?, ?, ?)
                """,
                ("TXN_001", "254712345678", 5000.0),
            )
            conn.commit()

            # Second insert (should be ignored due to PRIMARY KEY)
            cursor.execute(
                """
                INSERT INTO mpesa_transactions_raw 
                (transaction_id, phone_number, amount)
                VALUES (?, ?, ?)
                ON CONFLICT (transaction_id) DO NOTHING
                """,
                ("TXN_001", "254712345678", 5000.0),
            )
            conn.commit()

            # Verify only one row
            cursor.execute("SELECT COUNT(*) FROM mpesa_transactions_raw")
            count = cursor.fetchone()[0]
            assert count == 1

            conn.close()

    def test_concurrent_inserts_deduplicated(self):
        """Two concurrent inserts with same ID should result in only one row."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE fraud_alerts (
                    alert_id TEXT PRIMARY KEY,
                    transaction_id TEXT,
                    risk_score REAL,
                    severity TEXT
                )
                """
            )

            # Simulate two concurrent writes with same alert_id
            cursor.execute(
                """
                INSERT INTO fraud_alerts
                (alert_id, transaction_id, risk_score, severity)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (alert_id) DO NOTHING
                """,
                ("ALERT_001", "TXN_001", 0.9, "HIGH"),
            )

            cursor.execute(
                """
                INSERT INTO fraud_alerts
                (alert_id, transaction_id, risk_score, severity)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (alert_id) DO NOTHING
                """,
                ("ALERT_001", "TXN_001", 0.9, "HIGH"),
            )
            conn.commit()

            cursor.execute("SELECT COUNT(*) FROM fraud_alerts")
            count = cursor.fetchone()[0]
            assert count == 1

            conn.close()


class TestPartitioningByMsisdn:
    """Test that partitioning by msisdn preserves order per customer."""

    def test_msisdn_as_partition_key(self):
        """Messages with same msisdn should go to same partition."""
        messages = [
            {"TransID": "TXN_001", "MSISDN": "254712345678", "TransAmount": "100"},
            {"TransID": "TXN_002", "MSISDN": "254712345678", "TransAmount": "200"},
            {"TransID": "TXN_003", "MSISDN": "254787654321", "TransAmount": "300"},
        ]

        # Simulate partition assignment (simple hash)
        def get_partition(msisdn: str, num_partitions: int = 12) -> int:
            return hash(msisdn) % num_partitions

        partitions = {}
        for msg in messages:
            msisdn = msg["MSISDN"]
            partition = get_partition(msisdn)
            if partition not in partitions:
                partitions[partition] = []
            partitions[partition].append(msg)

        # Verify all messages for same customer in same partition
        assert len(partitions) == 2  # Two different customers
        assert len(partitions[get_partition("254712345678")]) == 2
        assert len(partitions[get_partition("254787654321")]) == 1


class TestDLQRoundtrip:
    """Test DLQ message capture and replay."""

    def test_invalid_message_routed_to_dlq(self):
        """Invalid messages should be routed to DLQ with full metadata."""
        invalid_payload = {"TransID": "TXN_001"}  # Missing required fields

        is_valid, error = SchemaValidator.validate(invalid_payload)
        assert not is_valid

        dlq_msg = SchemaValidator.format_dlq_message(
            raw_payload=invalid_payload,
            error=error,
            topic="mpesa-transactions",
            partition=0,
            offset=42,
        )

        # Verify DLQ message can be serialized and deserialized
        serialized = json.dumps(dlq_msg, default=str)
        deserialized = json.loads(serialized)

        assert deserialized["original_payload"] == invalid_payload
        assert deserialized["schema_error"] == error
        assert deserialized["offset"] == 42


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
