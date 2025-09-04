from pathlib import Path
import os, sys, time, subprocess
from TestAgent.ExternalDummies import TopicCreation

PKG_DEV_DIR = Path(__file__).resolve().parent
DOCKER_COMPOSE = PKG_DEV_DIR / "Kafka" / "docker-compose.yml"

def _resolve_port_and_persist():
    """env > ./kafka_port.json > default. Persist if env provided."""
    project_dir = Path.cwd()
    cfg_file = project_dir / "kafka_port.json"
    default_port = "9095"

    saved = None
    if cfg_file.exists():
        try:
            import json
            saved = json.loads(cfg_file.read_text()).get("port")
        except Exception:
            saved = None

    env_port = os.getenv("KAFKA_LOCAL_PORT")
    port = env_port or saved or default_port

    if env_port:
        try:
            cfg_file.write_text(f'{{"port":"{port}"}}')
        except Exception:
            pass

    env = os.environ.copy()
    env["KAFKA_LOCAL_PORT"] = port
    os.environ.update(env)  # ensure current process sees it too
    return port, env

def _wait_and_create_topics(cfg_path_str, env, retries=12, delay_s=5):
    for i in range(retries):
        try:
            TopicCreation.main(cfg_path_str)  # reads env via config.py
            print(f"✅ Topics created (attempt {i+1}).")
            return
        except Exception as e:
            if i == retries - 1:
                print(f"❌ Failed to create topics after {retries} attempts: {e}")
                raise
            time.sleep(delay_s)

def start():
    port, env = _resolve_port_and_persist()
    if not DOCKER_COMPOSE.exists():
        print(f"❌ compose not found: {DOCKER_COMPOSE}")
        sys.exit(1)

    print(f"🚀 Starting Kafka on port {port}...")
    subprocess.run(["docker", "compose", "-f", str(DOCKER_COMPOSE), "up", "-d"], check=True, env=env)

    project_cfg = Path.cwd() / "config.py"
    cfg_path = project_cfg if project_cfg.exists() else (PKG_DEV_DIR.parent / "config.py")
    print(f"📄 Using config: {cfg_path}")
    _wait_and_create_topics(str(cfg_path), env)
    print("🎉 Broker and topics ready.")

def stop():
    if not DOCKER_COMPOSE.exists():
        print(f"❌ compose not found: {DOCKER_COMPOSE}")
        sys.exit(1)
    print("🛑 Stopping Kafka...")
    subprocess.run(["docker", "compose", "-f", str(DOCKER_COMPOSE), "down", "-v"], check=True)
    print("✅ Stopped.")

def run_agent():
    """Use saved port/env; run the agent in-process."""
    port, env = _resolve_port_and_persist()
    os.environ.update(env)  # ensure current proc sees KAFKA_LOCAL_PORT

    from pathlib import Path
    project_cfg = Path.cwd() / "config.py"

    # Import here (after env set) to avoid early imports and to ensure config logic sees env
    from TestAgent.test_agent import main as agent_main

    print(f"▶️  Running agent on port {port}...")
    # Simulate CLI: pass project config if present
    sys.argv = ["run-testAgent"] + ([str(project_cfg)] if project_cfg.exists() else [])
    agent_main()