# TestAgent

Kafka-based test agent framework.

---

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/<your-org>/<your-repo>.git
cd <your-repo>
```

### 2. Create & activate a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate      # macOS/Linux
# .\\venv\\Scripts\\activate  # Windows PowerShell
```

### 3. Install in editable mode
```bash
pip install -e .
```

This installs all dependencies and makes the following commands available:
- `start-broker`
- `stop-broker`
- `run-testAgent`
- `send-dummy-message`

---

## 🐳 Running Kafka Broker

### Start broker (with chosen port)
```bash
KAFKA_LOCAL_PORT=9094 start-broker
```

- Spins up ZooKeeper, Kafka, and Kafka-UI via Docker Compose.
- Auto-creates topics:
  - `svt.test-agent.request`
  - `svt.test-agent.request.reply`
  - `svt.test-agent.status`
- Saves the chosen port (here 9094) to `./kafka_port.json`.
- Next runs will reuse this port automatically.

### Stop broker
```bash
stop-broker
```

Stops containers and removes volumes.

---

## 🧪 Running the Agent

From your project folder:
```bash
run-testAgent
```

- Connects to Kafka using the port saved in `./kafka_port.json`.
- Uses your local `config.py` if present, otherwise falls back to the package default.
- Subscribes to `svt.test-agent.request`.

---

## 📤 Sending a Test Message

Prepare a JSON file (e.g. `test_message.json`) with a command payload:

```json
{
  "command": "RunTest",
  "testId": "001",
  "data": {
    "params": {
      "chipName": "SLDO"
    }
  }
}
```

Send it to the agent:
```bash
send-dummy-message test_message.json
```

- Automatically picks `./config.py` and the saved Kafka port.
- Or specify explicitly:
```bash
send-dummy-message config.py test_message.json
```

---

## 📊 Kafka UI

Kafka-UI runs on [http://localhost:8088](http://localhost:8088) by default.  
Use it to browse topics, partitions, and messages.

---

## ⚡ Commands Recap

| Command             | Description                                       |
|---------------------|---------------------------------------------------|
| `start-broker`      | Start Kafka broker and create topics              |
| `stop-broker`       | Stop Kafka broker and remove volumes              |
| `run-testAgent`     | Run the agent with saved port/config              |
| `send-dummy-message`| Send a JSON test message to the agent’s request topic |

---

## 🛠 Development Notes

- Extend handlers in **`TestAgent/cmd_handler.py`**.
- Register them in **`TestAgent/Registries/registryOfCommands.py`**.
- Define test metadata in **`TestAgent/Registries/registryOfTests.py`**.
- Validation logic is in **`TestAgent/Registries/validateTests.py`**.

---

## 📋 Requirements

- Python 3.8+
- Docker + Docker Compose
- Virtual environment (`venv`) recommended

---