"""
DB Client — fetch chip metadata via Kafka (or stub).

This module provides a single public function:

    fetch_from_db(chip_ids, timeout_s=5.0, use_kafka=False, request_topic=None, reply_topic=None)

- In stub mode (default), it returns a deterministic 'Success' reply for quick dev cycles.
- In Kafka mode (use_kafka=True), it sends a structured request to the DB agent and
  waits for a correlated reply on the reply topic.

Expected Kafka exchange: Example

  Outgoing (to DB_REQUEST_TOPIC):
    {
      "type": "GetAllTests",
      "data": { "filter": { "Chipids": [<ids>] } },
      "corrId": "<uuid>"
    }

  Incoming (from DB_REPLY_TOPIC):
    {
      "status": "Success",
      "type": "GetAllTestsReply",
      "data": { "items": [ { "id": 0, "chipname": "SLDO", ... } ] },
      "corrId": "<uuid>"
    }
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from confluent_kafka import Producer, Consumer, KafkaException

# Try to import config from package; fall back to local module if running loose
try:
    from TestAgent import config as cfg  # type: ignore
except Exception:
    import config as cfg  # type: ignore

logger = logging.getLogger("DBClient")
logger.setLevel(logging.INFO)

JsonDict = Dict[str, Any]


# --------------------------------------------------------------------------------------
# Kafka helpers
# --------------------------------------------------------------------------------------
def _make_producer() -> Producer:
    """Create a Kafka producer using the app's configured producer settings."""
    return Producer(cfg.KAFKA_CONFIG["producer"])


def _make_consumer(group_suffix: str = "dbclient") -> Consumer:
    """
    Create a unique consumer group so each call sees fresh replies.
    Ensures we don't race with old offsets.
    """
    cconf = dict(cfg.KAFKA_CONFIG["consumer"])
    base_gid = cconf.get("group.id", "test-agent")
    cconf["group.id"] = f"{base_gid}-{group_suffix}-{uuid.uuid4().hex[:6]}"
    cconf["auto.offset.reset"] = "earliest"
    return Consumer(cconf)


def _resolve_topics(request_topic: Optional[str], reply_topic: Optional[str]) -> tuple[str, str]:
    """
    Resolve DB request/reply topics. If not provided, use defaults or values from config.py (if defined).
    """
    req = request_topic or getattr(cfg, "DB_REQUEST_TOPIC", "svt.db-agent.request")
    rep = reply_topic or getattr(cfg, "DB_REPLY_TOPIC", "svt.db-agent.request.reply")
    return req, rep


def _send_request_and_wait(
    chip_ids: List[int],
    timeout_s: float,
    request_topic: str,
    reply_topic: str,
) -> JsonDict:
    """
    Send a DB fetch request and block until a correlated reply arrives or times out.
    """
    producer = _make_producer()
    consumer = _make_consumer()
    corr_id = uuid.uuid4().hex
    req_payload: JsonDict = {
        "type": "GetAllTests",
        "data": {"filter": {"Chipids": chip_ids}},
        "corrId": corr_id,
    }

    deadline = time.time() + timeout_s

    try:
        # Subscribe to reply topic *before* producing a request minimizes race windows
        consumer.subscribe([reply_topic])

        # Send request
        producer.produce(request_topic, value=json.dumps(req_payload))
        producer.flush(2.0)
        logger.info("➡️  DB request sent to %s: %s", request_topic, req_payload)

        # Poll for correlated reply
        while time.time() < deadline:
            msg = consumer.poll(0.5)
            if msg is None:
                continue
            if msg.error():
                logger.warning("DB reply topic error: %s", msg.error())
                continue

            try:
                payload = json.loads(msg.value().decode("utf-8"))
            except Exception:
                logger.exception("Invalid JSON payload from DB reply topic")
                continue

            if payload.get("corrId") != corr_id:
                # Not for us; ignore
                continue

            logger.info("DB reply received: %s", payload)
            return payload

        # Timeout → return standardized failure
        err = {
            "status": "Fail",
            "type": "GetAllTestsReply",
            "error": f"DB reply timeout after {timeout_s}s",
            "corrId": corr_id,
        }
        logger.error("%s", err["error"])
        return err

    except KafkaException as ke:
        logger.exception("Kafka error during DB request")
        return {
            "status": "Fail",
            "type": "GetAllTestsReply",
            "error": f"KafkaException: {ke}",
            "corrId": corr_id,
        }
    except Exception as e:
        logger.exception("Unexpected error during DB request")
        return {
            "status": "Fail",
            "type": "GetAllTestsReply",
            "error": str(e),
            "corrId": corr_id,
        }
    finally:
        try:
            consumer.close()
        except Exception:
            pass


# --------------------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------------------
def fetch_from_db(
    chip_ids: Any,
    timeout_s: float = 5.0,
    use_kafka: bool = False,
    request_topic: Optional[str] = None,
    reply_topic: Optional[str] = None,
) -> JsonDict:
    """
    Fetch chip metadata from the DB agent.

    Args:
        chip_ids: int or list[int] — which chip ids to fetch
        timeout_s: maximum time to wait for reply (Kafka mode)
        use_kafka: if False (default), returns a stub success reply (fast dev mode)
        request_topic: override DB request topic (defaults from config or sensible default)
        reply_topic: override DB reply topic (defaults from config or sensible default)

    Returns:
        A dict shaped like:
        {
          "status": "Success" | "Fail",
          "type": "GetAllTestsReply",
          "data": { "items": [ { "id": <int>, "chipname": <str>, ... }, ... ] },
          "corrId": "<uuid>"   # Only present in Kafka mode
        }
    """
    # Normalize chip_ids to a list of ints
    if isinstance(chip_ids, list):
        ids = [int(x) for x in chip_ids if x is not None]
    elif chip_ids is None:
        ids = []
    else:
        ids = [int(chip_ids)]

    # -----------------------------
    # Stub mode (fast and predictable)
    # -----------------------------
    if not use_kafka:
        # Provide a simple success response; expand as needed
        first_id = ids[0] if ids else 0
        reply: JsonDict = {
            "status": "Success",
            "type": "GetAllTestsReply",
            "data": {"items": [{"id": first_id, "chipname": "SLDO"}]},
        }
        logger.info("(stub) DB reply: %s", reply)
        return reply

    # -----------------------------
    # Kafka mode
    # -----------------------------
    req_topic, rep_topic = _resolve_topics(request_topic, reply_topic)
    return _send_request_and_wait(ids, timeout_s, req_topic, rep_topic)