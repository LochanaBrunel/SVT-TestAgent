from __future__ import annotations

import copy
import logging
from typing import Any, Dict, Generator, Iterable, Tuple

from TestAgent.db_client import fetch_from_db
from TestAgent.testsystem_client import TestSystemClient
from TestAgent.Registries.validateTests import validate, validate_test_values

# --------------------------------------------------------------------------------------
# Logger / Client
# --------------------------------------------------------------------------------------
logger = logging.getLogger("CmdHandler")
logger.setLevel(logging.INFO)

_client = TestSystemClient()

# --------------------------------------------------------------------------------------
# Types
# --------------------------------------------------------------------------------------
JsonDict = Dict[str, Any]
GenTriple = Generator[Tuple[Any, str, str], None, None]  # (values_or_error, testStatus, statusMsg)

# --------------------------------------------------------------------------------------
# Small utilities
# --------------------------------------------------------------------------------------
def _reply(
    stream: bool,
    cmd_type: str,
    *,
    status: str,
    values: Any = None,
    status_msg: str | None = None,
    error: Any = None,
    payload_key: str = "testValues",
) -> JsonDict:
    """
    Build a consistent reply payload.
    - stream=False → <Cmd>Reply
    - stream=True  → <Cmd>StreamReply
    - payload_key: the success payload field ("testValues" by default, but "data" for e.g. GetAllTests)
    """
    suffix = "StreamReply" if stream else "Reply"
    out: JsonDict = {
        "type": f"{cmd_type}{suffix}",
        "testStatus": status,
    }

    if status == "TestRunning":
        out[payload_key] = values
        if status_msg:
            out["statusMsg"] = status_msg

    elif status == "TestSuccess":
        out[payload_key] = values

    elif status == "TestFail":
        # Either outputs-as-fail (e.g. Abort) or a proper error
        if isinstance(values, dict) and values.get("outputs") == "testAborted":
            out[payload_key] = values
        else:
            out["testError"] = error if error is not None else values
        if status_msg:
            out["statusMsg"] = status_msg

    return out


def _extract_and_strip_iterations(data: JsonDict | None, default: int = 1) -> tuple[int, JsonDict]:
    """
    Look for iterations in both `data` and `data['params']`.
    Tolerate the accidental 'ïterations'. Remove it from the returned dict.
    """
    if not isinstance(data, dict):
        return default, {}

    cleaned = copy.deepcopy(data)
    containers = [cleaned, cleaned.get("params", {}) if isinstance(cleaned.get("params"), dict) else {}]

    found = None
    for container in containers:
        if not isinstance(container, dict):
            continue
        for key in ("iterations", "ïterations"):
            if key in container:
                found = container.pop(key, None)
                break
        if found is not None:
            break

    if found is None:
        it = default
    else:
        try:
            it = int(found)
        except Exception:
            it = default

    return max(1, it), cleaned


def _validate_like_run_test(data: JsonDict) -> Tuple[bool, str | None, JsonDict]:
    """
    Reuse the RunTest schema for validation (caller decides what to include/exclude).
    Returns: (is_valid, error_msg, corrected_command)
    """
    is_valid, error_msg, corrected = validate({
        "command": "RunTest",
        "data": data,
        "testId": (data or {}).get("testId", "unknown"),
    })
    return is_valid, error_msg, corrected


def _stream_generator_as_replies(
    gen: Iterable[Tuple[Any, str, str]],
    cmd_type: str,
    *,
    corrected_command_for_outputs: JsonDict | None = None,
    payload_key: str = "testValues",
) -> Generator[JsonDict, None, None]:
    """
    Convert the 3-tuple stream from TestSystemClient into agent reply dicts.
    Optionally validate/correct outputs against schema before final success reply.
    """
    for values_or_err, test_status, status_msg in gen:
        if test_status == "TestRunning":
            yield _reply(True, cmd_type, status="TestRunning", values=values_or_err, status_msg=status_msg, payload_key=payload_key)

        elif test_status == "TestSuccess":
            if corrected_command_for_outputs is not None:
                # Validate/correct outputs (units, shapes) before final reply
                _, __, corrected_vals = validate_test_values(corrected_command_for_outputs, values_or_err)
                yield _reply(False, cmd_type, status="TestSuccess", values=corrected_vals, payload_key=payload_key)
            else:
                yield _reply(False, cmd_type, status="TestSuccess", values=values_or_err, payload_key=payload_key)

        elif test_status == "TestFail":
            # Fail may be a true error or an abort payload with outputs='testAborted'
            yield _reply(False, cmd_type, status="TestFail", values=values_or_err, error=values_or_err, status_msg=status_msg, payload_key=payload_key)


# --------------------------------------------------------------------------------------
# Public handlers (called by TestAgent)
# All handlers accept a single 'data: dict' argument to keep TestAgent generic.
# --------------------------------------------------------------------------------------
def GetAllTests(data: JsonDict | None = None) -> JsonDict:
    """
    Steps:
      1) Read chipId(s) from data.filter.chipId
      2) Query DB agent → resolve chipname
      3) Ask TestSystemClient for tests for that chip (from registryOfTests)
      4) Return a standard reply in `data`, not `testValues`
    """
    data = data or {}
    chip_ids = (data.get("filter", {}) or {}).get("chipId", [])
    if not isinstance(chip_ids, list):
        chip_ids = [chip_ids]

    db_reply = fetch_from_db(chip_ids)
    if db_reply.get("status") != "Success":
        logger.error("GetAllTests: DB query failed: %s", db_reply)
        return _reply(False, "GetAllTests", status="TestFail", error=f"DB query failed: {db_reply}", payload_key="data")

    items = ((db_reply.get("data") or {}).get("items") or [])
    if not items:
        return _reply(False, "GetAllTests", status="TestFail", error="DB returned no items", payload_key="data")

    chip_name = items[0].get("chipname", "")
    if not chip_name:
        return _reply(False, "GetAllTests", status="TestFail", error="DB reply missing 'chipname'", payload_key="data")

    tests_info = _client.get_all_tests(chip_name)
    return _reply(False, "GetAllTests", status="TestSuccess", values=tests_info, payload_key="data")


def RunTest(data: JsonDict) -> Generator[JsonDict, None, None]:
    """
    Single test run.
    Validation is performed here (not in TestAgent).
    Streams progress replies; ends with success/fail.
    """
    is_valid, error_msg, corrected_cmd = _validate_like_run_test(data)
    if not is_valid:
        logger.error("RunTest validation failed: %s", error_msg)
        yield _reply(False, "RunTest", status="TestFail", error=error_msg)
        return

    params = (corrected_cmd.get("data") or {}).get("params", {}) if isinstance(corrected_cmd.get("data"), dict) else {}
    chip_type = params.get("chipName", "")
    test_name = params.get("testName", "")

    logger.info("RunTest: chip=%s test=%s", chip_type, test_name)

    gen = _client.run_test(chip_type, test_name, params)

    # For final success reply, validate outputs against schema using the corrected command.
    yield from _stream_generator_as_replies(
        gen,
        "RunTest",
        corrected_command_for_outputs=corrected_cmd,
        payload_key="testValues",
    )


def RunLoopTest(data: JsonDict) -> Generator[JsonDict, None, None]:
    """
    Validates input like RunTest but *excludes* 'iterations' during validation.
    Then runs TestSystemClient.run_loop_test(...) with the validated params + iterations.
    """
    # 1) Extract and remove iterations (from either data or params)
    iterations, data_no_iter = _extract_and_strip_iterations(data, default=1)

    # 2) Validate
    is_valid, error_msg, corrected_cmd = _validate_like_run_test(data_no_iter)
    if not is_valid:
        logger.error("RunLoopTest validation failed: %s", error_msg)
        yield _reply(False, "RunLoopTest", status="TestFail", error=error_msg)
        return

    corrected_params = {}
    if isinstance(corrected_cmd.get("data"), dict):
        corrected_params = corrected_cmd["data"].get("params", {}) or {}

    chip_type = corrected_params.get("chipName", "")
    test_name = corrected_params.get("testName", "")

    logger.info("RunLoopTest: chip=%s test=%s iterations=%d", chip_type, test_name, iterations)

    gen = _client.run_loop_test(chip_type, test_name, corrected_params, iterations)

    # Minimal wrapper for validating outputs against schema on final success
    minimal_cmd_for_outputs = {"command": "RunTest", "data": {"params": corrected_params}}
    yield from _stream_generator_as_replies(
        gen,
        "RunLoopTest",
        corrected_command_for_outputs=minimal_cmd_for_outputs,
        payload_key="testValues",
    )


def AbortTest(data: JsonDict | Any) -> JsonDict:
    test_id = data.get("testId") if isinstance(data, dict) else data
    return _client.abort_test(test_id)


def TestStatus(data: JsonDict | Any) -> JsonDict:
    test_id = data.get("testId") if isinstance(data, dict) else data
    return _client.test_status(test_id)


def RunTestPlan(data: JsonDict) -> JsonDict:
    params = data.get("params", {}) if isinstance(data, dict) else {}
    plan_name = params.get("planName", "")
    return _client.run_test_plan(plan_name, params)