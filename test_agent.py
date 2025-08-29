import json
import logging
import pdb
import types
import os, sys, importlib.util, argparse
from confluent_kafka import Consumer, Producer, KafkaException
from Registries.registryOfCommands import DEFAULT_COMMAND_HANDLERS, CHIP_COMMAND_OVERRIDES
from Registries.validateTests import validate

logger = logging.getLogger("TestAgent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")



class TestAgent:
    def __init__(self, local_mode=False, debug_msg=None):
        self.local_mode = local_mode
        self.debug_msg = debug_msg

        if not self.local_mode:
            logger.info("Initializing Kafka TestAgent...")
            self.consumer = Consumer(KAFKA_CONFIG["consumer"])
            logger.info("Kafka Consumer created with config: %s", KAFKA_CONFIG["consumer"])
            self.producer = Producer(KAFKA_CONFIG["producer"])
            logger.info("Kafka Producer created with config: %s", KAFKA_CONFIG["producer"])
            self.consumer.subscribe([REQUEST_TOPIC])
            logger.info("Subscribed to topic: %s", REQUEST_TOPIC)
        else:
            logger.info("Running in LOCAL DEBUG MODE (Kafka disabled).")

    def start(self):
        if self.local_mode:
            logger.info("Processing debug message locally...")
            self._process_command(self.debug_msg)
            return

        logger.info("TestAgent started")
        idle_logged = False
        try:
            while True:
                msg = self.consumer.poll(timeout=0.5)
                if msg is None:
                    if not idle_logged:
                        logger.info("TestAgent idling, listening for commands...")
                        idle_logged = True
                    continue
                idle_logged = False
                if msg.error():
                    logger.error(f"Kafka error: {msg.error()}")
                    continue
                try:
                    command = json.loads(msg.value().decode("utf-8"))
                    self._process_command(command)
                except json.JSONDecodeError:
                    logger.error("Invalid JSON in message")
                except Exception:
                    logger.exception("Unexpected error processing message")
        except KeyboardInterrupt:
            logger.info("Shutting down TestAgent...")
        finally:
            if not self.local_mode:
                logger.info("Closing Kafka consumer and flushing producer...")
                self.consumer.close()
                self.producer.flush(timeout=10)
                logger.info("Agent shut down cleanly.")

    def _process_command(self, command: dict):
        logger.info("Processing command: %s", command)
        cmd_type = command.get("command")
        data = command.get("data", {})
        test_id = command.get("testId", "unknown")
        #pdb.set_trace()
        #Validation message
        is_msg_valid, error_msg = validate(command)
        if is_msg_valid:

            try:
                # Extract chipName safely
                try:
                    chip_name = data.get("params", {}).get("chipName", "")
                except Exception:
                    chip_name = ""

                # Get combined command handlers for the chip
                handlers = self.get_command_handlers_for_chip(chip_name)
                handler = handlers.get(cmd_type)

                if not handler:
                    response = {
                        "test_id": test_id,
                        "agentStatus": "TestAgentFail",
                        "agentError": f"Unknown command type: {cmd_type}",
                    }
                    return self._send_response(response, is_stream=False)

                response = handler(data)

                # If handler is a generator   
                if isinstance(response, types.GeneratorType):
                    for r in response:
                        response = {**r, "test_id": test_id, "agentStatus": "TestAgentSuccess"}
                        self._send_response(response, is_stream=(response["type"].endswith("StreamReply")))
                        
                else:
                    response = {**r, "test_id": test_id, "agentStatus": "TestAgentSuccess"}
                    self._send_response(response, is_stream=False)

            except Exception as e:
                response = {
                    "test_id": test_id,
                    "agentStatus": "TestAgentFail",
                    "agentError": str(e),
                }
        else:
            logger.error(f"Kafka message is not recognized by the TestAgent : {error_msg}")




    def get_command_handlers_for_chip(self, chip_name: str):
        chip_commands = CHIP_COMMAND_OVERRIDES.get(chip_name, {})
        combined = {**DEFAULT_COMMAND_HANDLERS, **chip_commands}
        return combined

    def _delivery_report(self, err, msg):
        if err:
            logger.error(f"Delivery failed: {err}")
        else:
            logger.info(f"Delivered message to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")

    def _send_response(self, response, is_stream):
        #pdb.set_trace()  # for debugging
        topic = STATUS_TOPIC if is_stream else REPLY_TOPIC
        if self.local_mode:
            logger.info("LOCAL RESPONSE: %s", json.dumps(response, indent=2))
            return

        if response.get("agentStatus") == "TestAgentFail": 
            logger.error(f"Test {test_id} failed due to {response.get('agentStatus')}: {response.get('agentError')}, not sending success reply.")
        elif response.get("testStatus") == "TestFail": 
            test_error = response.get(testError)
            logger.warning(f"Test {test_id} failed due to test system error: {test_error}, not sending success reply.")
        else:
            self.producer.produce(
                topic,
                key=str(response["test_id"]),
                value=json.dumps(response),
                callback=self._delivery_report,
            )
            self.producer.poll(0.1)


def load_config(path):
    if not os.path.isabs(path):
        base = os.path.dirname(__file__)
        path = os.path.join(base, path)

    spec = importlib.util.spec_from_file_location("custom_config", path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config




if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", action="store_true", help="Run without Kafka, process local JSON")
    parser.add_argument("--json", type=str, help="Path to JSON file with test command")
    parser.add_argument("config_file", nargs="?", help="Config file path")
    args = parser.parse_args()

    if args.local:
        if not args.json:
            logger.error("In --local mode you must provide --json <file>")
            sys.exit(1)
        with open(args.json) as f:
            debug_msg = json.load(f)
        agent = TestAgent(local_mode=True, debug_msg=debug_msg)
    else:
        if args.config_file:
            config = load_config(args.config_file)
        else:
            from . import config
        REQUEST_TOPIC = config.REQUEST_TOPIC
        REPLY_TOPIC = config.REPLY_TOPIC
        STATUS_TOPIC = config.STATUS_TOPIC
        KAFKA_CONFIG = config.KAFKA_CONFIG
        agent = TestAgent()

    agent.start()