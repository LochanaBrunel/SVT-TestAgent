"""
TestAgent: Generic Kafka router that dispatches 'command' to registered handlers,
streams replies or single replies to Kafka, and stays free of validation logic.

- Handlers are resolved from registry (DEFAULT_COMMAND_HANDLERS + chip overrides).
- Streaming replies are detected via `type` suffix "*StreamReply" and sent to STATUS_TOPIC.
- Non-stream replies go to REPLY_TOPIC.
- Flexible request-id detection: one of requestId / Unique_id / id / testId.
- Local mode: no Kafka, logs replies to console.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import signal
import sys
import types
from typing import Any, Dict, Optional

from confluent_kafka import Consumer, Producer
from TestAgent.Registries.registryOfCommands import (
    DEFAULT_COMMAND_HANDLERS,
    CHIP_COMMAND_OVERRIDES,
)

# --------------------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------------------
logger = logging.getLogger("TestAgent")
# Only set basicConfig if root logging isn't already configured elsewhere.
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

# --------------------------------------------------------------------------------------
# Types & helpers
# --------------------------------------------------------------------------------------
JsonDict = Dict[str, Any]
KafkaCfg = Dict[str, Dict[str, Any]]
TopicsCfg = Dict[str, str]

# Allow flexible message ids (so envelope schema can evolve)
REQUEST_ID_KEYS = ("requestId", "Unique_id", "id", "testId")


def _extract_request_id(message: JsonDict, default: str = "unknown") -> str:
    """Support multiple request id field names to make the envelope schema flexible."""
    for k in REQUEST_ID_KEYS:
        if k in message:
            try:
                return str(message[k])
            except Exception:
                pass
    return default


def _extract_chip_name(data: JsonDict) -> str:
    """
    Best-effort chip name extractor:
    expects chip name at data.params.chipName.
    Returns empty string if not present; agent remains generic.
    """
    try:
        params = data.get("params") or {}
        return str(params.get("chipName") or "")
    except Exception:
        return ""


def _is_stream_reply(reply: JsonDict) -> bool:
    """
    Decide if a reply is a streaming update by checking type suffix "*StreamReply".
    Example: "RunTestStreamReply" → True
    """
    t = reply.get("type")
    return isinstance(t, str) and t.endswith("StreamReply")


def _load_config_module(path: str):
    """Load a config .py file from absolute or relative path."""
    abspath = os.path.abspath(path)
    spec = importlib.util.spec_from_file_location("custom_config", abspath)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load config module from: {path}")
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


# --------------------------------------------------------------------------------------
# Agent
# --------------------------------------------------------------------------------------
class TestAgent:
    """
    Generic Kafka agent that:
      - listens on REQUEST_TOPIC,
      - routes 'command' to handlers (from registry),
      - streams or replies messages to the appropriate topic,
      - does not validate payloads (handlers do).
    """

    def __init__(
        self,
        topics_cfg: TopicsCfg,
        kafka_cfg: KafkaCfg,
        *,
        local_mode: bool = False,
        debug_msg: Optional[JsonDict] = None,
        poll_timeout: float = 0.5,
    ):
        self.local_mode = local_mode
        self.debug_msg = debug_msg
        self.poll_timeout = poll_timeout

        self.REQUEST_TOPIC = topics_cfg["REQUEST_TOPIC"]
        self.REPLY_TOPIC = topics_cfg["REPLY_TOPIC"]
        self.STATUS_TOPIC = topics_cfg["STATUS_TOPIC"]
        self.KAFKA_CONFIG = kafka_cfg

        self.consumer: Optional[Consumer] = None
        self.producer: Optional[Producer] = None

        # Graceful shutdown flag
        self._running = True
        signal.signal(signal.SIGINT, self._handle_signal)   # Ctrl+C
        signal.signal(signal.SIGTERM, self._handle_signal)  # kill/terminate

        if not self.local_mode:
            self._init_kafka()
        else:
            logger.info("Running in LOCAL DEBUG MODE (Kafka disabled).")

    # ----------------------------
    # Initialization & lifecycle
    # ----------------------------
    def _init_kafka(self) -> None:
        """Create Kafka consumer/producer and subscribe to request topic."""
        logger.info("Initializing Kafka TestAgent...")
        try:
            self.consumer = Consumer(self.KAFKA_CONFIG["consumer"])
            logger.info("Kafka Consumer created with config: %s", self.KAFKA_CONFIG["consumer"])

            self.producer = Producer(self.KAFKA_CONFIG["producer"])
            logger.info("Kafka Producer created with config: %s", self.KAFKA_CONFIG["producer"])

            self.consumer.subscribe([self.REQUEST_TOPIC])
            logger.info("Subscribed to topic: %s", self.REQUEST_TOPIC)
        except Exception:
            logger.exception("Failed to initialize Kafka client(s)")
            raise

    def _handle_signal(self, signum, frame) -> None:
        logger.info("Received signal %s → stopping agent loop...", signum)
        self._running = False

    def start(self) -> None:
        """
        Main loop: poll Kafka (or process a single local message), dispatch to handler,
        and publish responses.
        """
        if self.local_mode:
            logger.info("Processing debug message locally...")
            self._process_command(self.debug_msg or {})
            return

        logger.info("TestAgent started (request topic: %s)", self.REQUEST_TOPIC)
        idle_logged = False

        try:
            while self._running:
                msg = self.consumer.poll(timeout=self.poll_timeout) if self.consumer else None

                if msg is None:
                    if not idle_logged:
                        logger.info("TestAgent idling, listening for commands...")
                        idle_logged = True
                    continue

                idle_logged = False

                if msg.error():
                    logger.error("Kafka error: %s", msg.error())
                    continue

                try:
                    payload = msg.value()
                    if payload is None:
                        logger.warning("Received empty Kafka message")
                        continue

                    command = json.loads(payload.decode("utf-8"))
                    self._process_command(command)

                except json.JSONDecodeError:
                    logger.error("Invalid JSON in message")
                except Exception:
                    logger.exception("Unexpected error decoding/processing message")

        finally:
            self._shutdown()

    def _shutdown(self) -> None:
        """
        Close consumer and flush producer to ensure all messages are delivered.
        """
        if self.local_mode:
            logger.info("Agent shut down (local mode).")
            return

        try:
            if self.consumer is not None:
                logger.info("Closing Kafka consumer ...")
                self.consumer.close()
            if self.producer is not None:
                logger.info("Flushing Kafka producer ...")
                self.producer.flush(timeout=10)
        except Exception:
            logger.exception("Error during shutdown")
        finally:
            logger.info("Agent shut down cleanly.")

    # ----------------------------
    # Message handling
    # ----------------------------
    def _process_command(self, command: JsonDict) -> None:
        """
        Resolve handler by command name; allow chip-specific overrides; call handler with `data`.
        Augment handler replies with request id and agent status. Publish them.
        """
        logger.info("Processing command: %s", command)

        cmd_type = str(command.get("command") or "").strip()
        data = command.get("data") or {}
        req_id = _extract_request_id(command, default="unknown")

        if not cmd_type:
            logger.error("Missing 'command' field in message")
            self._send_response({
                "test_id": req_id,
                "agentStatus": "TestAgentFail",
                "agentError": "Missing 'command' field"
            })
            return

        try:
            chip_name = _extract_chip_name(data)
            handler = self._resolve_handler(cmd_type, chip_name)

            if handler is None:
                self._send_response({
                    "test_id": req_id,
                    "agentStatus": "TestAgentFail",
                    "agentError": f"Unknown command type: {cmd_type}",
                })
                return

            result = handler(data)

            # Stream generator
            if isinstance(result, types.GeneratorType):
                for reply in result:
                    resp_obj = {
                        **(reply or {}),
                        "test_id": req_id,
                        "agentStatus": "TestAgentSuccess",
                    }
                    self._send_response(resp_obj)
            else:
                # Single reply
                resp_obj = {
                    **(result or {}),
                    "test_id": req_id,
                    "agentStatus": "TestAgentSuccess",
                }
                self._send_response(resp_obj)

        except Exception as e:
            logger.exception("Handler error")
            self._send_response({
                "test_id": req_id,
                "agentStatus": "TestAgentFail",
                "agentError": str(e),
            })

    def _resolve_handler(self, cmd_type: str, chip_name: str):
        """
        Merge default handlers + chip-specific overrides and return the function for cmd_type.
        """
        chip_commands = CHIP_COMMAND_OVERRIDES.get(chip_name, {}) or {}
        handlers = {**DEFAULT_COMMAND_HANDLERS, **chip_commands}
        return handlers.get(cmd_type)

    # ----------------------------
    # Response publishing
    # ----------------------------
    def _delivery_report(self, err, msg) -> None:
        if err:
            logger.error("Delivery failed: %s", err)
        else:
            logger.info(
                "Delivered message to %s [%s] @ offset %s",
                msg.topic(), msg.partition(), msg.offset()
            )

    def _send_response(self, response: JsonDict) -> None:
        """
        Decide topic automatically based on reply type (*StreamReply → STATUS_TOPIC; else → REPLY_TOPIC).
        Drop 'agentStatus' before publishing normal replies (keep for internal logs).
        """
        # Local mode: just log the message (useful for offline dev).
        if self.local_mode:
            logger.info("LOCAL RESPONSE: %s", json.dumps(response, indent=2))
            return

        # If the agent itself failed, don't send a fake success reply
        if response.get("agentStatus") == "TestAgentFail":
            logger.error(
                "Request %s failed: %s",
                response.get("test_id"), response.get("agentError")
            )
            return

        topic = self.STATUS_TOPIC if _is_stream_reply(response) else self.REPLY_TOPIC

        # Don't leak 'agentStatus' in public replies
        pub = dict(response)
        pub.pop("agentStatus", None)

        try:
            assert self.producer is not None, "Producer not initialized"
            self.producer.produce(
                topic,
                key=str(pub.get("test_id", "")),
                value=json.dumps(pub),
                callback=self._delivery_report,
            )
            self.producer.poll(0.1)  # serve delivery callbacks
        except Exception:
            logger.exception("Error producing Kafka message")


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Run the TestAgent.")
    parser.add_argument("--local", action="store_true", help="Run without Kafka; process local JSON (--json).")
    parser.add_argument("--json", type=str, help="Path to JSON file with test command (only with --local).")
    parser.add_argument("config_file", nargs="?", help="Path to config.py file (if omitted, uses package default).")
    args = parser.parse_args()

    if args.local:
        if not args.json:
            logger.error("In --local mode you must provide --json <file>")
            sys.exit(1)
        with open(args.json) as f:
            debug_msg = json.load(f)

        # Use package default topics/config (structure only; Kafka unused in local mode)
        from TestAgent import config as default_cfg  # type: ignore
        topics_cfg: TopicsCfg = {
            "REQUEST_TOPIC": default_cfg.REQUEST_TOPIC,
            "REPLY_TOPIC": default_cfg.REPLY_TOPIC,
            "STATUS_TOPIC": default_cfg.STATUS_TOPIC,
        }
        kafka_cfg: KafkaCfg = default_cfg.KAFKA_CONFIG

        agent = TestAgent(topics_cfg, kafka_cfg, local_mode=True, debug_msg=debug_msg)
        agent.start()
        return

    # Kafka mode
    if args.config_file:
        cfg = _load_config_module(args.config_file)
    else:
        from TestAgent import config as cfg  # type: ignore

    topics_cfg: TopicsCfg = {
        "REQUEST_TOPIC": cfg.REQUEST_TOPIC,
        "REPLY_TOPIC": cfg.REPLY_TOPIC,
        "STATUS_TOPIC": cfg.STATUS_TOPIC,
    }
    kafka_cfg: KafkaCfg = cfg.KAFKA_CONFIG

    agent = TestAgent(topics_cfg, kafka_cfg, local_mode=False)
    agent.start()


if __name__ == "__main__":
    main()