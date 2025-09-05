# TestAgent/testsystem_client.py
"""
TestSystemClient
================

This module provides a high-level **facade** for interacting with different
test system backends (emulator or real hardware).

- Backends implement the ITestBackend interface (see backends/interface.py).
- The client keeps an `abort` flag that backends must check during long runs.
- Handlers in cmd_handler.py call into this client (not directly into backends).
- Which backend to use is configured in config.py or set dynamically.

The design lets you start with an EmulatorBackend, then switch to a
RealBackend later without changing your cmd_handler or agent.
"""

import logging
import threading
import importlib
from typing import Any, Dict, Iterable, Optional, Tuple

from TestAgent.Registries.registryOfTests import CHIP_TEST_DEFINITIONS
from TestAgent.testSystemBackend.interface import ITestBackend
from TestAgent.testSystemBackend.emulator import EmulatorBackend  # Default fallback

# --------------------------------------------------------------------------------------
# Logger
# --------------------------------------------------------------------------------------
logger = logging.getLogger("TestSystemClient")
logger.setLevel(logging.INFO)

# --------------------------------------------------------------------------------------
# Type Aliases
# --------------------------------------------------------------------------------------
JsonDict = Dict[str, Any]
# Each backend yields triples: (values_or_error, status, message)
# status ∈ {"TestRunning", "TestSuccess", "TestFail"}
GenTriple = Iterable[Tuple[Any, str, str]]

# --------------------------------------------------------------------------------------
# Backend Loader
# --------------------------------------------------------------------------------------
def load_backend_from_path(class_path: str, **kwargs) -> ITestBackend:
    """
    Dynamically import and instantiate a backend.

    Args:
        class_path: Dotted path to class
            e.g. "TestAgent.backends.real_backend.RealBackend"
        **kwargs: Constructor keyword arguments passed to the backend class.

    Returns:
        An instantiated backend object implementing ITestBackend.
    """
    module_path, cls_name = class_path.rsplit(".", 1)
    mod = importlib.import_module(module_path)
    cls = getattr(mod, cls_name)
    return cls(**kwargs)

# --------------------------------------------------------------------------------------
# Facade Client
# --------------------------------------------------------------------------------------
class TestSystemClient:
    """
    Facade for test system backends.

    Usage:
        client = TestSystemClient()                       # uses EmulatorBackend by default
        client.use_backend_from_config(cfg.BACKEND)       # switch to real backend from config
        for result in client.run_test("SLDO", "PowerRampUp", params):
            print(result)

    Notes:
    - This class is intentionally *lightweight*.
    - It does not implement validation or schema enforcement.
    - It is only responsible for orchestrating backend execution and
      providing a stable API to cmd_handler.
    """

    def __init__(self, backend: Optional[ITestBackend] = None):
        """
        Initialize the client.

        Args:
            backend: Optional backend to use. If not provided, defaults to EmulatorBackend.
        """
        self._backend: ITestBackend = backend or EmulatorBackend()
        self._abort = threading.Event()  # Flag to signal abort requests
        logger.info("TestSystemClient using backend: %s", type(self._backend).__name__)

    # ------------------------------------------------------------------
    # Backend Management
    # ------------------------------------------------------------------
    def set_backend(self, backend: ITestBackend):
        """
        Switch to a new backend instance at runtime.

        Args:
            backend: An object implementing ITestBackend.
        """
        self._backend = backend
        logger.info("Backend switched to: %s", type(self._backend).__name__)

    def use_backend_from_config(self, backend_spec: Dict[str, Any]):
        """
        Switch backend using a config dictionary.

        Example:
            backend_spec = {
                "class": "TestAgent.backends.emulator.EmulatorBackend",
                "kwargs": {}
            }

            backend_spec = {
                "class": "TestAgent.backends.real_backend.RealBackend",
                "kwargs": {"host": "10.0.0.5", "token": "..."}
            }

        Args:
            backend_spec: Dict with keys:
                - "class": dotted import path to backend class
                - "kwargs": optional dict of constructor args
        """
        cls_path = backend_spec.get("class")
        kwargs   = backend_spec.get("kwargs", {})
        if cls_path:
            be = load_backend_from_path(cls_path, **kwargs)
            self.set_backend(be)

    # ------------------------------------------------------------------
    # Registry Queries
    # ------------------------------------------------------------------
    def get_all_tests(self, chip_name: str) -> JsonDict:
        """
        Query registryOfTests.py for all tests defined for a given chip.

        Args:
            chip_name: Name of the chip (e.g. "SLDO").

        Returns:
            Dict: {"chipName": chip_name, "tests": [list of test names]}
        """
        chip_def = CHIP_TEST_DEFINITIONS.get(chip_name, {}) or {}
        return {"chipName": chip_name, "tests": list((chip_def.get("tests") or {}).keys())}

    # ------------------------------------------------------------------
    # Control Plane
    # ------------------------------------------------------------------
    def abort_test(self, test_id: Any) -> JsonDict:
        """
        Signal an abort to the running test.

        The backend must check `_abort.is_set()` periodically and
        return early with a "TestFail" + {"outputs": "testAborted"} payload.

        Args:
            test_id: Identifier of the test to abort.

        Returns:
            JSON dict reply (to be sent back to Kafka).
        """
        self._abort.set()
        msg = f"Aborted {test_id}"
        logger.warning(msg)
        return {"type": "AbortTestReply", "testStatus": "TestSuccess", "statusMsg": msg}

    def test_status(self, test_id: Any) -> JsonDict:
        """
        Lightweight status probe. Could be wired to backend if needed.

        Args:
            test_id: Identifier of the test.

        Returns:
            Dict indicating current status.
        """
        return {"type": "TestStatusReply", "testStatus": "TestRunning", "statusMsg": f"Test {test_id}: Running"}

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def run_test(self, chip_type: str, test_name: str, params: JsonDict) -> GenTriple:
        """
        Run a single test using the current backend.

        Args:
            chip_type: e.g. "SLDO"
            test_name: e.g. "PowerRampUp"
            params: parameters for the test (inputs/configurations)

        Yields:
            Triples (values_or_error, testStatus, message) until completion.
        """
        self._abort.clear()
        try:
            # Step 1: Initialize backend (may raise)
            self._backend.initialize(chip_type, test_name, params, self._abort)
        except Exception as e:
            err = f"Initialization failed: {e}"
            logger.exception(err)
            yield err, "TestFail", err
            return

        # Step 2: Stream execution results from backend
        for values_or_err, status, msg in self._backend.run(chip_type, test_name, params, self._abort):
            yield values_or_err, status, msg
            if status in ("TestSuccess", "TestFail"):
                break

    def run_loop_test(self, chip_type: str, test_name: str, params: JsonDict, iterations: int) -> GenTriple:
        """
        Run the same test multiple times in sequence.

        Args:
            chip_type: e.g. "SLDO"
            test_name: test name
            params: test parameters
            iterations: number of iterations

        Yields:
            Triples from each iteration. Each iteration is treated as a new test instance.
        """
        for i in range(int(iterations)):
            self._abort.clear()
            iter_name = f"{test_name}_iter{i+1}"
            logger.info("%s %s loop %d/%d", chip_type, test_name, i + 1, iterations)
            yield from self.run_test(chip_type, iter_name, params)