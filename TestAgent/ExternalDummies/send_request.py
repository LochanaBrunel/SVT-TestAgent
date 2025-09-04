import json
import os
import sys
import importlib.util
from pathlib import Path
from confluent_kafka import Producer


# -------------------- helpers --------------------

def _inject_saved_port():
    """If KAFKA_LOCAL_PORT not set, use ./kafka_port.json if present."""
    if os.environ.get("KAFKA_LOCAL_PORT"):
        return
    cfg = Path.cwd() / "kafka_port.json"
    if cfg.exists():
        try:
            port = json.loads(cfg.read_text()).get("port")
            if port:
                os.environ["KAFKA_LOCAL_PORT"] = str(port)
        except Exception:
            pass  # non-fatal

def _auto_config_path() -> str:
    """Prefer ./config.py; else fallback to packaged TestAgent/config.py."""
    project_cfg = Path.cwd() / "config.py"
    if project_cfg.exists():
        return str(project_cfg)
    # package default: TestAgent/config.py
    return str(Path(__file__).resolve().parents[2] / "config.py")

def _load_config(path: str):
    spec = importlib.util.spec_from_file_location("custom_config", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# -------------------- core send --------------------

def send_request(config_module, message: dict):
    """
    Send a single message to REQUEST_TOPIC using config_module.KAFKA_CONFIG.
    """
    producer_cfg = config_module.KAFKA_CONFIG["producer"]
    topic = config_module.REQUEST_TOPIC

    p = Producer(producer_cfg)

    def _delivery_report(err, msg):
        if err:
            print(f"❌ Delivery failed: {err}")
        else:
            print(f"✅ Delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")

    payload = json.dumps(message)
    p.produce(topic, key=str(message.get("testId", "dummy")), value=payload, callback=_delivery_report)
    p.poll(0)
    p.flush()


# -------------------- CLI --------------------

def main():
    """
    Usage:
      send-dummy-message <message.json>
      send-dummy-message <config.py> <message.json>
    """
    args = sys.argv[1:]

    if len(args) == 1:
        msg_path = Path(args[0])
        cfg_path = Path(_auto_config_path())
    elif len(args) == 2:
        cfg_path = Path(args[0])
        msg_path = Path(args[1])
    else:
        print("Usage: send-dummy-message <message.json>  OR  send-dummy-message <config.py> <message.json>")
        sys.exit(1)

    if not msg_path.exists():
        print(f"❌ Message file not found: {msg_path}")
        sys.exit(1)
    if not cfg_path.exists():
        print(f"❌ Config file not found: {cfg_path}")
        sys.exit(1)

    # ensure KAFKA_LOCAL_PORT is available even if user didn't export it
    _inject_saved_port()

    config = _load_config(str(cfg_path))
    with open(msg_path) as f:
        msg = json.load(f)

    print(f"➡️  Sending message to {config.REQUEST_TOPIC} via {config.KAFKA_CONFIG['producer']['bootstrap.servers']}")
    send_request(config, msg)
    print(f"✅ Sent message from {msg_path} using config {cfg_path}")


if __name__ == "__main__":
    main()