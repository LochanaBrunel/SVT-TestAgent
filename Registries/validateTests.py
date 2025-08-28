from .registryOfTests import CHIP_TEST_DEFINITIONS

def validate(command):
    
    try:
        data = command["data"]
        params = data["params"]

        chip_name = params["chipName"]
        test_name = params["testName"]
        test_config = params.get("TestConfiguration", {})
        inputs = params.get("inputs", {})

        # === Chip-level validation ===
        if chip_name not in CHIP_TEST_DEFINITIONS:
            raise ValueError(f"Unsupported chip: {chip_name}")
        
        chip_def = CHIP_TEST_DEFINITIONS[chip_name]
        chip_defaults = chip_def.get("default", {})
        chip_tests = chip_def.get("Tests", {})

        if test_name not in chip_tests:
            raise ValueError(f"Unsupported test '{test_name}' for chip '{chip_name}'")
        
        test_def = chip_tests[test_name]

        # === Merged schema (defaults overridden by test-specific definitions) ===
        expected_config_keys = _merge_keys("TestConfiguration", chip_defaults, test_def)
        expected_input_keys = _merge_keys("inputs", chip_defaults, test_def)

        check_fields("TestConfiguration", test_config, expected_config_keys)
        check_fields("inputs", inputs, expected_input_keys)

        return True, ""  # success

    except KeyError as e:
        return False, f"Missing required key in test command: {e}"
    except ValueError as e:
        return False, str(e)

def validate_test_values(test_values, chip_name, test_name):
    try:
        if chip_name not in CHIP_TEST_DEFINITIONS:
            return False, f"Unknown chip: {chip_name}"

        chip_def = CHIP_TEST_DEFINITIONS[chip_name]
        chip_defaults = chip_def.get("default", {})
        chip_tests = chip_def.get("Tests", {})


        if test_name not in chip_tests:
            return False, f"Unknown test '{test_name}' for chip '{chip_name}'"

        test_def = chip_tests[test_name]
        expected_tv_inputs = _merge_keys("inputs", chip_defaults.get("testValues", {}), test_def.get("testValues", {}))
        expected_tv_outputs = _merge_keys("outputs", chip_defaults.get("testValues", {}), test_def.get("testValues", {}))

        check_fields("testValues.inputs", test_values.get("inputs", {}), expected_tv_inputs)
        check_fields("testValues.outputs", test_values.get("outputs", {}), expected_tv_outputs)

        return True, ""

    except KeyError as e:
        return False, f"Missing key in testValues: {e}"
    except ValueError as e:
        return False, str(e)

def _merge_keys(field, defaults, overrides):
    """Merge default and override keys for a given section."""
    default_keys = set(defaults.get(field, [])) if isinstance(defaults, dict) else set()
    override_keys = set(overrides.get(field, [])) if isinstance(overrides, dict) else set()
    return default_keys.union(override_keys)


def check_fields(section_name, actual_dict, expected_keys):
    actual_keys = set(actual_dict.keys())
    missing = expected_keys - actual_keys
    extra = actual_keys - expected_keys

    if missing:
        raise ValueError(f"{section_name}: Missing fields: {missing}")
    if extra:
        raise ValueError(f"{section_name}: Unexpected fields: {extra}")
