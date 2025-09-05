# TestAgent/backends/real_backend.py
import logging, threading
from typing import Any, Dict, Iterable, Tuple, Optional
from .interface import ITestBackend

logger = logging.getLogger("RealBackend")
JsonDict = Dict[str, Any]

class ConnectionHandle:
    """
    Placeholder for your real connection (REST/gRPC/socket/DLL/etc.).
    Fill methods with your actual implementation later.
    """
    def __init__(self, **kwargs):
        self.connected = False
        self.kwargs = kwargs

    def connect(self):
        # TODO: open session/authenticate/etc.
        # e.g., self.session = requests.Session(); self.session.post(...)
        self.connected = True

    def close(self):
        # TODO: cleanly close/cleanup
        self.connected = False

    def start_job(self, chip_type: str, test_name: str, params: JsonDict) -> str:
        # TODO: send job to your system and return job_id
        return "job-123"

    def get_status(self, job_id: str) -> Dict[str, Any]:
        # TODO: poll your system for status/results
        # Return shape suggestion:
        # { "running": True/False, "success": True/False, "message": str,
        #   "results": {"inputs": {...}, "outputs": {...}} or
        #   "error": "..." }
        return {"running": False, "success": True, "message": "Completed", "results": {"inputs": {}, "outputs": {}}}

    def cancel_job(self, job_id: str):
        # TODO: send cancel/abort signal to system
        pass


class RealBackend(ITestBackend):
    """
    Real system backend.
    Uses ConnectionHandle (placeholder) so you can keep connection details undecided for now.
    """

    def __init__(self, **conn_kwargs):
        self._conn_kwargs = conn_kwargs
        self._conn: Optional[ConnectionHandle] = None
        self._job_id: Optional[str] = None

    def _ensure_connected(self):
        if self._conn is None:
            self._conn = ConnectionHandle(**self._conn_kwargs)
            self._conn.connect()
            logger.info("RealBackend connected with %s", self._conn_kwargs)
        elif not self._conn.connected:
            self._conn.connect()
            logger.info("RealBackend reconnected")

    def initialize(self, chip_type: str, test_name: str, params: JsonDict, abort: threading.Event) -> None:
        self._ensure_connected()
        if abort.is_set():
            return
        logger.info("RealBackend: initialize %s/%s with params=%s", chip_type, test_name, params)

    def run(self, chip_type: str, test_name: str, params: JsonDict, abort: threading.Event) -> Iterable[Tuple[Any, str, str]]:
        self._ensure_connected()

        # 1) start job
        self._job_id = self._conn.start_job(chip_type, test_name, params)
        logger.info("RealBackend: started job %s", self._job_id)

        # 2) poll
        while True:
            if abort.is_set():
                try:
                    self._conn.cancel_job(self._job_id)
                except Exception:
                    logger.exception("Cancel job failed")
                values = {"inputs": params.get("inputs", {}), "outputs": "testAborted"}
                yield values, "TestFail", "Aborted by user"
                return

            try:
                st = self._conn.get_status(self._job_id)
            except Exception as e:
                logger.exception("Status poll error")
                yield str(e), "TestFail", "Polling error"
                return

            if st.get("running"):
                yield "Running...", "TestRunning", st.get("message", "Running...")
            elif st.get("success"):
                results = st.get("results", {})
                # Expect {"inputs": {...}, "outputs": {...}}
                if "inputs" not in results:
                    results["inputs"] = params.get("inputs", {})
                yield results, "TestSuccess", st.get("message", "Completed")
                return
            else:
                err = st.get("error", "Test failed")
                yield err, "TestFail", st.get("message", "Failed")
                return