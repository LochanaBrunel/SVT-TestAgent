"""
Registry of command handlers.

- Dynamically imports all functions from `TestAgent.cmd_handler`.
- Provides DEFAULT_COMMAND_HANDLERS: the standard mapping from command string → handler function.
- Supports chip-specific overrides via CHIP_COMMAND_OVERRIDES.
- Utility `newTest` helps register additional custom handlers easily.

Usage:
    from TestAgent.Registries.registryOfCommands import DEFAULT_COMMAND_HANDLERS, CHIP_COMMAND_OVERRIDES
"""

import importlib
import inspect
from typing import Callable, Dict

# --------------------------------------------------------------------------------------
# Load cmd_handler module dynamically
# --------------------------------------------------------------------------------------
cmd_handler_module = importlib.import_module("TestAgent.cmd_handler")

# Collect all functions defined in cmd_handler
ALL_HANDLERS: Dict[str, Callable] = {
    name: obj
    for name, obj in inspect.getmembers(cmd_handler_module, inspect.isfunction)
}


# --------------------------------------------------------------------------------------
# Helper
# --------------------------------------------------------------------------------------
def newTest(testName: str) -> Dict[str, Callable]:
    """
    Return a single-entry dict mapping a testName to its handler function.
    Useful for extending CHIP_COMMAND_OVERRIDES with new tests.

    Example:
        CHIP_COMMAND_OVERRIDES["SLDO"].update(newTest("CustomTest"))
    """
    if testName not in ALL_HANDLERS:
        raise ValueError(
            f"Handler '{testName}' not found in TestAgent/cmd_handler.py. "
            f"Available handlers: {list(ALL_HANDLERS.keys())}"
        )
    return {testName: ALL_HANDLERS[testName]}


# --------------------------------------------------------------------------------------
# Default command handlers
# --------------------------------------------------------------------------------------
DEFAULT_COMMAND_HANDLERS: Dict[str, Callable] = {
    "GetAllTests": ALL_HANDLERS.get("GetAllTests"),
    "RunTest": ALL_HANDLERS.get("RunTest"),
    "AbortTest": ALL_HANDLERS.get("AbortTest"),
    "TestStatus": ALL_HANDLERS.get("TestStatus"),
    "RunLoopTest": ALL_HANDLERS.get("RunLoopTest"),
    "RunTestPlan": ALL_HANDLERS.get("RunTestPlan"),
}


# --------------------------------------------------------------------------------------
# Chip-specific command overrides
# --------------------------------------------------------------------------------------
CHIP_COMMAND_OVERRIDES: Dict[str, Dict[str, Callable]] = {
    "SLDO": {
        # Example of adding a chip-specific handler:
        # **newTest("CustomSLDOTest")
    },
    "NVG": {
        # Add NVG-specific overrides here
    },
}