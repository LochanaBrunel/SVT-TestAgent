# TestAgent/backends/interface.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, Tuple
import threading

JsonDict = Dict[str, Any]

class ITestBackend(ABC):
    """
    Contract for test system backends:
      - initialize(): prepare the system for a given test
      - run(): execute the test and yield (values_or_error, status, message)
        where status ∈ {"TestRunning", "TestSuccess", "TestFail"}
      - Must honor `abort.is_set()` to stop early.
    """

    @abstractmethod
    def initialize(
        self, chip_type: str, test_name: str, params: JsonDict, abort: threading.Event
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def run(
        self, chip_type: str, test_name: str, params: JsonDict, abort: threading.Event
    ) -> Iterable[Tuple[Any, str, str]]:
        raise NotImplementedError