# SLDO Test Agent

This provides a clean separation between messaging, logic, database access, and test system interaction  

---

## Project Structure


sldo_agent/
│
├── __init__.py           # Package marker
├── sldo_agent.py         # Main agent (Kafka consumer/producer, command dispatcher)
├── cmd_handler.py        # Logic for each command (run_test, fetch_db, retrive_db.)
├── db_client.py          # Database client (abstracts queries, error handling)
├── ts_client.py          # Interface to instruments / hardware test system
├── config.py             # Centralized config (Kafka topics, DB settings, retries)
└── utils.py              # Helpers (logging wrappers, validation, error formatting)

## TODO

# Step1

1. Describe the commands
2. Describe the message json structure

# Step 2 

1. Write separate codes to decode messages and pass commands. 

# Step 3

1. Link decodes with agents to pass to clients

