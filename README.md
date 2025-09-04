
# TestAgent

Kafka-based test agent framework with Dockerized Kafka/ZooKeeper and pluggable test command handlers.

---

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/<your-org>/<your-repo>.git
cd SVT-TestAgent

2. Create & activate a virtual environment

python3 -m venv venv
source venv/bin/activate      # macOS/Linux
# .\venv\Scripts\activate     # Windows PowerShell

3. Install in editable mode

pip install -e .

This installs dependencies and makes the following commands available globally in your venv:
	•	start-broker
	•	stop-broker
	•	run-testAgent
	•	send-dummy-message

⸻

🐳 Running Kafka Broker

Start broker (with chosen port)

KAFKA_LOCAL_PORT=<any_prefered_port> start-broker

	•	Spins up ZooKeeper, Kafka, and Kafka-UI via Docker Compose.
	•	Auto-creates topics:
	•	svt.test-agent.request
	•	svt.test-agent.request.reply
	•	svt.test-agent.status
	•	Saves the chosen port (e.g. 9094) into ./kafka_port.json.
	•	Next runs will reuse this port automatically.

Stop broker

stop-broker

Stops and cleans up all Kafka/ZooKeeper containers and volumes.

⸻

🧪 Running the Agent

From your project folder (with your own config.py):

run-testAgent

	•	Connects to Kafka using the port saved in ./kafka_port.json.
	•	Uses your local config.py if present (project-based config).
	•	Subscribes to the svt.test-agent.request topic.

⸻

📤 Sending a Test Message

Create a JSON payload (e.g. test_message.json):

{
  "command": "RunTest",
  "testId": "001",
  "data": {
    "params": {
      "chipName": "SLDO"
    }
  }
}

Send it:

send-dummy-message test_message.json

	•	Defaults to ./config.py + saved port.
	•	Or specify config explicitly:

send-dummy-message config.py test_message.json


⸻

📊 Kafka UI

Kafka-UI runs on http://localhost:8088.
Use it to browse topics, partitions, offsets, and messages.

⸻

⚡ Commands Recap

Command	Description
start-broker	Start Kafka broker and auto-create topics
stop-broker	Stop Kafka broker and remove volumes
run-testAgent	Run the agent with project config.py + saved port
send-dummy-message	Send a JSON test message to the agent’s request topic


⸻

🛠 Development Notes
	•	Extend handlers in TestAgent/cmd_handler.py.
	•	Register handlers in TestAgent/Registries/registryOfCommands.py.
	•	Define test metadata in TestAgent/Registries/registryOfTests.py.
	•	Add validation rules in TestAgent/Registries/validateTests.py.
	•	Broker startup/shutdown is handled via TestAgent/Dev/startup.py.

⸻

📋 Requirements
	•	Python 3.8+
	•	Docker + Docker Compose
	•	Virtual environment (venv) recommended

⸻