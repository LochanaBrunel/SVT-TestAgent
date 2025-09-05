import json
import logging
import sys
import importlib.util
from confluent_kafka import Producer, Consumer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RequestSender")

def load_config(path):
    """Dynamically import a config module from a given file path."""
    spec = importlib.util.spec_from_file_location("config", path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config

def delivery_report(err, msg):
    if err:
        logger.error(f"Delivery failed: {err}")
    else:
        logger.info(f"Message delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")

def send_request(json_file: str, config, wait_for_reply=True):
    REQUEST_TOPIC = config.REQUEST_TOPIC
    REPLY_TOPIC = config.REPLY_TOPIC

    # Load request from file
    with open(json_file, "r") as f:
        request = json.load(f)

    producer = Producer(config.KAFKA_CONFIG["producer"])
    consumer = None

    if wait_for_reply:
        consumer = Consumer(config.KAFKA_CONFIG["consumer"])
        consumer.subscribe([REPLY_TOPIC])

    headers = [
        ("cmdType", str(request.get("command", ""))),
        ("correlationId", str(request.get("testId", ""))),
        ("replyTopic", str(REPLY_TOPIC)),
    ]

    producer.produce(
        REQUEST_TOPIC,
        key=str(request.get("testId")),
        value=json.dumps(request),
        headers=headers,
        callback=delivery_report
    )
    producer.flush()

    if wait_for_reply:
        logger.info("Waiting for reply...")
        while True:
            msg = consumer.poll(timeout=5.0)
            if msg is None:
                logger.warning("No reply yet...")
                continue
            if msg.error():
                logger.error(f"Consumer error: {msg.error()}")
                continue

            response = json.loads(msg.value().decode("utf-8"))
            if response.get("request_id") == request.get("request_id"):
                logger.info(f"Received reply: {json.dumps(response, indent=2)}")
                break

        consumer.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 send_request.py <config_file.py> <message_file.json>")
        sys.exit(1)

    config_path = sys.argv[1]
    message_file = sys.argv[2]

    config = load_config(config_path)
    send_request(message_file, config, wait_for_reply=False)