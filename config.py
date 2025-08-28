# Hard-coded topics for your requirement
REQUEST_TOPIC = "svt.test-agent.request"
REPLY_TOPIC = "svt.test-agent.request.reply"
STATUS_TOPIC = "svt.test-agent.request.reply"

# Kafka config – change bootstrap.servers if needed
KAFKA_CONFIG = {
    "consumer": {
        "bootstrap.servers": "localhost:9095",   # if running on host
        "group.id": "test-agent",
        "auto.offset.reset": "earliest",
    },
    "producer": {
        "bootstrap.servers": "localhost:9095",
    }
}
