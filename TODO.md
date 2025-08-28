Step 1 — **Define Commands**
    Document all supported command types (e.g. run_test, fetch_db, retrieve_data, etc).
    Define the expected JSON message structure for each command.

Step 2 — **Implement Message Decoding**
    Write dedicated utilities to decode incoming Kafka messages.
    Validate input (types, required fields) and normalize before dispatch.

Step 3 — **Connect Components**
	Integrate the decoding layer with the agent dispatcher.
	Route commands to the correct client (db_client, ts_client) via cmd_handler.