# TestAgent/backends/emulator.py
import time, logging, threading
from typing import Any, Dict, Iterable, Tuple
from .interface import ITestBackend

logger = logging.getLogger("EmulatorBackend")
JsonDict = Dict[str, Any]

class EmulatorBackend(ITestBackend):
    def initialize(self, chip_type: str, test_name: str, params: JsonDict, abort: threading.Event) -> None:
        logger.info("Emulator: initialize chip=%s test=%s", chip_type, test_name)
        for _ in range(2):
            if abort.is_set():
                logger.warning("Emulator: init aborted")
                return
            time.sleep(0.01)

    def run(self, chip_type: str, test_name: str, params: JsonDict, abort: threading.Event) -> Iterable[Tuple[Any, str, str]]:
        inputs = (params.get("inputs") or {})
        v_in_target = float(inputs.get("vInTarget", 0.0))
        steps = [20, 40, 60, 80, 100]
        tick = 2.0 / 100.0  # 2 seconds total

        for i in range(1, 101):
            if abort.is_set():
                values = {"inputs": inputs, "outputs": "testAborted"}
                msg = f"TestFail: {chip_type} {test_name} aborted at {i}%."
                logger.warning(msg)
                yield values, "TestFail", msg
                return

            time.sleep(tick)

            if i in steps and v_in_target > 0:
                fraction = (i // 20) / 5
                ramped = round(fraction * v_in_target, 10)
                if ramped == v_in_target:
                    values = {"inputs": inputs, "outputs": {"vOut(V)": 1.3}}
                    msg = f"TestSuccess: {chip_type} {test_name} completed successfully."
                    logger.info(msg)
                    yield values, "TestSuccess", msg
                    return
                else:
                    msg = f"TestRunning: {chip_type} {test_name} completed up to {i}%."
                    logger.info(msg)
                    yield "Running...", "TestRunning", msg