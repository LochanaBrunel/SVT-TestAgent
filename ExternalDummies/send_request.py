import json
import logging
import pdb
from confluent_kafka import Producer, Consumer

REQUEST_TOPIC = "svt.test-agent.request"
REPLY_TOPIC = "svt.test-agent.request1.reply"

KAFKA_CONFIG = {
    "bootstrap.servers": "localhost:9095",
    "group.id": "test-client",
    "auto.offset.reset": "earliest",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RequestSender")


def delivery_report(err, msg):
    if err:
        logger.error(f"Delivery failed: {err}")
    else:
        logger.info(f"Message delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")


def send_request(json_file: str, wait_for_reply=True):
    # Load request from file
    with open(json_file, "r") as f:
        request = json.load(f)

    producer = Producer({"bootstrap.servers": KAFKA_CONFIG["bootstrap.servers"]})
    consumer = None

    if wait_for_reply:
        consumer = Consumer(KAFKA_CONFIG)
        consumer.subscribe([REPLY_TOPIC])

    # Build headers (can be dynamic or hard-coded)
    headers = [
        ("cmdType", str(request.get("command", ""))),
        ("correlationId", str(request.get("testId", ""))),
        ("replyTopic", str(REPLY_TOPIC)),
    ]

    # Produce request with key + headers
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
    send_request("SVT-Supervisor_dummy/test_message.json", wait_for_reply=False)