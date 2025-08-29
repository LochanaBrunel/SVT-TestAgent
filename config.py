import os
import json
from pathlib import Path

CONFIG_FILE = Path(__file__).with_name("kafka_port.json")

# default if nothing exists
default_port = "9095"

# load last saved port if exists
if CONFIG_FILE.exists():
    with open(CONFIG_FILE, "r") as f:
        saved_port = json.load(f).get("port", default_port)
else:
    saved_port = default_port

# override if env var set
KAFKA_LOCAL_PORT = os.getenv("KAFKA_LOCAL_PORT", saved_port)

# if env var was set, update persistence file
if os.getenv("KAFKA_LOCAL_PORT"):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"port": KAFKA_LOCAL_PORT}, f)

# Hard-coded topics for your requirement
REQUEST_TOPIC = "svt.test-agent.request"
REPLY_TOPIC = "svt.test-agent.request.reply"
STATUS_TOPIC = "svt.test-agent.request.reply"

# Kafka config – now dynamic port
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