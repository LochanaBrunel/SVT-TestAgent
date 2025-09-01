import time
import logging
from tqdm import tqdm

logger = logging.getLogger("TestSystemClient")
logger.setLevel(logging.INFO)


class TestSystemClient:
    """Client to interface with a hardware test system."""

    def __init__(self):
        logger.info("TestSystemClient instance created.")

    def initialize(self, chip_type: str, test_name: str) -> None:
        logger.info(f"Initializing test system for chip '{chip_type}' and test '{test_name}'...")
        time.sleep(0.02)
        logger.info(f"Initialization complete for {chip_type} ({test_name}).")

    def run_test(self, chip_type: str, test_name: str, params: dict):
        self.initialize(chip_type, test_name)
        inputs = params.get("inputs", {})
        testConfig= params.get("TestConfiguration", {})

        yield from self.test_system_interface(chip_type, test_name, inputs, testConfig)

    def test_system_interface(self, chip_type: str, test_name: str, inputs: dict, testConfig: dict) -> dict:
        #Send Chip name, test name with all the parameters to the dedicated test system. 
        """
        Emulated interface to the test system.
        In real system this would call the correct subsystem (e.g. SLDOTestSystem).
        """
        # Only for emulation
        testResult = 1.3
        testValues = {
            "inputs": inputs,
            "outputs": {
                "v_out(V)" : testResult
            }
        }

        # Parse vInTarget
        vInTarget_str = inputs.get("vInTarget", "0V").replace("V", "")
        try:
            vInTarget = float(vInTarget_str)
        except ValueError:
            vInTarget = 0.0

        # Stream progress from emulator
        for progMsg, testStatus in self._progress_emulator(2, vInTarget, chip_type, test_name, True):
            if testStatus == "TestRunning":
                testValue = "Running..."
                yield testValue, testStatus, progMsg
            elif testStatus == "TestSuccess":
                yield testValues, testStatus, progMsg
            elif testStatus == "TestFail":
                error = "Power supply issue"
                logger.warning(f"{testStatus}: {chip_type} {test_name} failed due to {error}.")
                yield error, testStatus, progMsg
    # ------------------------
    # Helper: Progress Emulator with Milestones  
    # ------------------------
    def _progress_emulator(self, duration: float = 2.0, vInTarget: float = 0.0, chip_type: str = "Unknown", test_name: str = "PowerRampUp" ,is_testFail=False):
        """

        Args:
            duration (float): Total duration of the progress (seconds) only in simulation.
            vInTarget (float): Input voltage target for milestone calculation.

        """
        steps = 100
        milestones = []
        progMsg=""
        checkpoints = [20, 40, 60, 80, 100]
        prev_val = None
        prev_status = None

        for i in range(1, steps + 1):
            time.sleep(duration / steps)

            if i in checkpoints and vInTarget > 0:
                fraction = (i // 20) / 5   # e.g. 20% → 0.2, 40% → 0.4
                ramped_val = round(fraction * vInTarget, 3)
                if i== 60 and is_testFail:
                    testStatus = "TestFail"
                    progMsg = f"{testStatus}: {chip_type} {test_name} stopped at {i}%."
                    logger.warning(progMsg)
                elif ramped_val == vInTarget:
                    testStatus = "TestSuccess"
                    progMsg = f"{testStatus}: {chip_type} {test_name} completed succesfully."
                    logger.info(progMsg)
                else:
                    testStatus = "TestRunning"
                    progMsg = f"{testStatus}: {chip_type} {test_name} completed upto {i}%."
                    logger.info(progMsg)

                

                # Yield only if something changed
                if ramped_val != prev_val or testStatus != prev_status:
                    
                    yield progMsg, testStatus
                    prev_val, prev_status = ramped_val, testStatus