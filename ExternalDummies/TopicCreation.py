import sys
from kafka.admin import KafkaAdminClient, NewTopic
import importlib.util

def load_config(path):
    """Dynamically import a config module from a given file path."""
    spec = importlib.util.spec_from_file_location("config", path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config

def create_topics(config):
    """Create topics defined in the config module."""
    bootstrap_servers = config.KAFKA_CONFIG["producer"]["bootstrap.servers"]
    topics = [config.REQUEST_TOPIC, config.REPLY_TOPIC]

    admin = KafkaAdminClient(bootstrap_servers=bootstrap_servers, client_id="topic_creator")

    new_topics = [
        NewTopic(name=topic, num_partitions=10, replication_factor=1)
        for topic in topics
    ]

    try:
        admin.create_topics(new_topics=new_topics, validate_only=False)
        print(f"✅ Topics created: {topics}")
    except Exception as e:
        print(f"⚠️ Error while creating topics: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 topicCreation.py <config_file.py>")
        sys.exit(1)

    config_path = sys.argv[1]
    config = load_config(config_path)
    create_topics(config)