from kafka.admin import KafkaAdminClient, NewTopic

def create_topics(bootstrap_servers="localhost:9095"):
    admin = KafkaAdminClient(bootstrap_servers=bootstrap_servers, client_id="topic_creator")

    topics = [
        "svt.test-agent.request",
        "svt.test-agent.request.reply"
    ]

    # Define topics with partitions and replication factor
    new_topics = [
        NewTopic(name=topic, num_partitions=10, replication_factor=1)
        for topic in topics
    ]

    try:
        admin.create_topics(new_topics=new_topics, validate_only=False)
        print(f"✅ Topics created: {topics}")
    except Exception as e:
        print(f"⚠️  Error while creating topics: {e}")

if __name__ == "__main__":
    create_topics()