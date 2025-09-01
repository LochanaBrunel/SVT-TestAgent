# SLDO Test Agent

A lightweight test agent for interacting with Kafka brokers, running test commands, and simulating requests.

---

## 🚀 Setup

### 1. Start Docker with Kafka
```bash
KAFKA_LOCAL_PORT=<preferred_port: default=9095> docker compose up -d
```

⚠️ **Note:**  
- Do **not** use port `9093` — it is reserved by Kafka UI.  
- If you need to reset/clean the containers (⚠️ **this will delete all broker messages**):
```bash
docker compose down -v
```

---

### 2. Create Kafka Topics
```bash
cd ExternalDummies
KAFKA_LOCAL_PORT=<preferred_port: default=9095> python3 TopicCreation.py config.py
```

- The `config.py` will remember the last port used.  
- To switch to a new port, set `KAFKA_LOCAL_PORT` again.  

---

### 3. Send Messages
1. Edit `ExternalDummies/test_message.json` with the desired request.  
2. Run:
```bash
cd ExternalDummies
python3 send_request.py ../config.py test_message.json
```

---

### 4. Run the Test Agent
```bash
python3 -m test_agent config.py
```

- You can provide different `config.py` files for different configurations.  
- Make sure the **`KAFKA_LOCAL_PORT`** matches your running broker.  

---

## 🧪 Local Mode (No Kafka Required)
For testing without involving a Kafka broker:
```bash
python3 -m test_agent_dev config.py --local --json ExternalDummies/test_message.json
```

This runs the agent locally using the given JSON message.  

---

## ⚙️ Notes
- Keep Kafka and agent configs in sync via `config.py`.  
- Cleaning containers (`docker compose down -v`) wipes broker state.  
