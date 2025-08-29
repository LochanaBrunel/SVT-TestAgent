import inspect
from db_client import fetch_from_db
from testsystem_client import TestSystemClient

client = TestSystemClient()

def GetAllTests():
    return client.get_all_tests()

def RunTest(data):
    """run test and collect all updates into a list."""
    params = data.get("params", {})
    chipType = params.get("chipName", "")
    testName = params.get("testName", "")
    cmd_type = inspect.currentframe().f_code.co_name
    for testValues, testStatus, statusMsg in client.run_test(chipType, testName, params):
        if testStatus == "TestRunning":
            response = {
                "type": f"{cmd_type}StreamReply",
                "testStatus": testStatus,
                "testValues": testValues,
                "statusMsg": statusMsg,
            }
            yield response

        elif testStatus == "TestSuccess":
            response = {
                "type": f"{cmd_type}Reply",
                "testStatus": testStatus,
                "testValues": testValues,
            }
            yield response
            return  # generator ends → agent knows test is complete

        elif testStatus == "TestFail":
            error = testValues
            response = {
                "type": f"{cmd_type}Reply",
                "testStatus": testStatus,
                "testError": error,
            }
            yield response  
            return  # generator ends → agent knows test is complete


def AbortTest(testId):
    return client.abort_test(testId)

def TestStatus(testId):
    return client.test_status(testId)

def RunLoopTest(chipType, testName, params, iterations):
    return client.run_loop_test(chipType, testName, params, iterations)

def RunTestPlan(planName, params):
    return client.run_test_plan(planName, params)