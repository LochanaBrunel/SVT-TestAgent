import os

# read from environment (startup sets this for you)
KAFKA_LOCAL_PORT = os.environ.get("KAFKA_LOCAL_PORT", "9095")

# topics
REQUEST_TOPIC = "svt.test-agent.request"
REPLY_TOPIC   = "svt.test-agent.request.reply"
STATUS_TOPIC  = "svt.test-agent.request.reply"  # (consider using a distinct status topic)

# Kafka config
KAFKA_CONFIG = {
    "consumer": {
        "bootstrap.servers": f"localhost:{KAFKA_LOCAL_PORT}",
        "group.id": "test-agent",
        "auto.offset.reset": "earliest",
    },
    "producer": {
        "bootstrap.servers": f"localhost:{KAFKA_LOCAL_PORT}",
    }
}