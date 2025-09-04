import importlib
import inspect

# Load all functions from cmd_handler module
cmd_handler_module = importlib.import_module("TestAgent.cmd_handler")

ALL_HANDLERS = {
    name: obj
    for name, obj in inspect.getmembers(cmd_handler_module, inspect.isfunction)
}

# Helper to fetch handler by name and return as a dict entry
def newTest(testName):
    if testName not in ALL_HANDLERS:
        raise ValueError(f"Handler '{testName}' not found in defined to TestAgent(cmd_handler.py) yet")
    return {testName: ALL_HANDLERS[testName]}

# Default command handlers
DEFAULT_COMMAND_HANDLERS = {
    "GetAllTests": ALL_HANDLERS.get("GetAllTests"),
    "RunTest": ALL_HANDLERS.get("RunTest"),
    "AbortTest": ALL_HANDLERS.get("AbortTest"),
    "TestStatus": ALL_HANDLERS.get("TestStatus"),
    "RunLoopTest": ALL_HANDLERS.get("RunLoopTest"),
    "RunTestPlan": ALL_HANDLERS.get("RunTestPlan"),
}

# Chip-specific command overrides
CHIP_COMMAND_OVERRIDES = {
    "SLDO": {
        
        #add any new tests like newTests("Test1", "Test2")).
    },
    "NVG": {
        
    }
}
