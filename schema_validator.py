"""
Schema validation for M-Pesa transactions.

Routes invalid or schema-drifted messages to a DLQ for inspection and replay.
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class SchemaValidator:
    """Validate incoming transaction payloads against expected schema."""

    # Expected schema (minimal required fields for fraud detection)
    REQUIRED_FIELDS = {
        "TransID",
        "MSISDN",
        "TransAmount",
        "TransTime",
    }

    OPTIONAL_FIELDS = {
        "BusinessShortCode",
        "AccountReference",
        "BillRefNumber",
    }

    @staticmethod
    def validate(payload: Any) -> Tuple[bool, Optional[str]]:
        """
        Validate transaction payload.

        Returns:
            (is_valid, error_message)
        """
        if not isinstance(payload, dict):
            return False, f"Payload is not a dict: {type(payload)}"

        # Check required fields
        missing = SchemaValidator.REQUIRED_FIELDS - set(payload.keys())
        if missing:
            return False, f"Missing required fields: {missing}"

        # Validate field types
        try:
            # TransID and MSISDN should be strings
            if not isinstance(payload.get("TransID"), str):
                return False, "TransID must be string"
            if not isinstance(payload.get("MSISDN"), str):
                return False, "MSISDN must be string"

            # TransAmount should be numeric (int or float or string representation)
            amount_val = payload.get("TransAmount")
            if isinstance(amount_val, str):
                float(amount_val)  # Will raise if not valid
            elif not isinstance(amount_val, (int, float)):
                return False, "TransAmount must be numeric or numeric string"

            # TransTime should be string (format not validated here, left to downstream)
            if not isinstance(payload.get("TransTime"), str):
                return False, "TransTime must be string"

        except (ValueError, TypeError) as e:
            return False, f"Type validation error: {e}"

        return True, None

    @staticmethod
    def format_dlq_message(
        raw_payload: Any,
        error: str,
        topic: str,
        partition: int,
        offset: int,
        timestamp: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Format a message for the DLQ topic."""
        return {
            "original_payload": raw_payload,
            "schema_error": error,
            "original_topic": topic,
            "partition": partition,
            "offset": offset,
            "timestamp": timestamp,
            "dlq_ingestion_timestamp": int(__import__("time").time() * 1000),
        }


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    valid = {
        "TransID": "TXN123",
        "MSISDN": "254712345678",
        "TransAmount": "1000",
        "TransTime": "20260101120000",
    }
    print("Valid payload:", SchemaValidator.validate(valid))

    invalid = {"TransID": "TXN123", "MSISDN": "254712345678"}  # missing TransAmount
    print("Invalid payload:", SchemaValidator.validate(invalid))
