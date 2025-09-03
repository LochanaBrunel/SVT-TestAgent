import logging
import re
from .registryOfTests import CHIP_TEST_DEFINITIONS

logger = logging.getLogger("TestSchemaValidation")
logger.setLevel(logging.INFO)

# --- Unit conversion map ---
UNIT_CONVERSIONS = {
    ("pF", "nF"): lambda v: v / 1000,
    ("nF", "pF"): lambda v: v * 1000,
    ("uF", "nF"): lambda v: v * 1000,
    ("nF", "uF"): lambda v: v / 1000,
    ("mV", "V"): lambda v: v / 1000,
    ("V", "mV"): lambda v: v * 1000,
    ("A", "mA"): lambda v: v * 1000,
    ("mA", "A"): lambda v: v / 1000,
    ("kV/s", "V/s"): lambda v: v * 1000,
    ("V/s", "kV/s"): lambda v: v / 1000,
    ("°C", "C"): lambda v: v,
}

# ----------------- Main validate -----------------
def validate(command):
    try:
        data = command["data"]
        params = data["params"]

        chip_name = params["chipName"]
        test_name = params["testName"]
        test_config = params.get("testConfiguration", {})
        inputs = params.get("inputs", {})

        logger.info(f"Validating command for chip='{chip_name}', test='{test_name}'")

        if chip_name not in CHIP_TEST_DEFINITIONS:
            raise ValueError(f"Unsupported chip: {chip_name}")
        chip_def = CHIP_TEST_DEFINITIONS[chip_name]
        chip_defaults = chip_def.get("default", {})
        chip_tests = chip_def.get("tests", {})

        if test_name not in chip_tests:
            raise ValueError(f"Unsupported test '{test_name}' for chip '{chip_name}'")
        test_def = chip_tests[test_name]

        # Merge defaults + test-specific
        expected_config = _merge_dict("testConfiguration", chip_defaults, test_def)
        expected_inputs = _merge_dict("inputs", chip_defaults, test_def)

        # Extract values from message
        test_config_clean, config_units = _extract_units(test_config)
        inputs_clean, inputs_units = _extract_units(inputs)

        # Apply defaults when not defined
        test_config_clean, config_units = _apply_defaults(expected_config, test_config_clean, "testConfiguration", config_units)
        inputs_clean, inputs_units = _apply_defaults(expected_inputs, inputs_clean, "inputs", inputs_units)

        # Correct units
        test_config_clean, config_units = _correct_units(test_config_clean, config_units, expected_config, "testConfiguration")
        inputs_clean, inputs_units = _correct_units(inputs_clean, inputs_units, expected_inputs, "inputs", strict=True)

        # Validate
        check_fields("testConfiguration", test_config_clean, expected_config, config_units)
        check_fields("inputs", inputs_clean, expected_inputs, inputs_units)

        # Rebuild corrected command WITHOUT units in keys
        corrected_params = {
            "chipName": chip_name,
            "testName": test_name,
            "testConfiguration": {k: v for k, v in test_config_clean.items()},
            "inputs": {k: v for k, v in inputs_clean.items()}
        }

        corrected_command = {**command, "data": {**data, "params": corrected_params}}

        logger.info("Validation successful")
        return True, "", corrected_command

    except KeyError as e:
        logger.error(f"Validation failed: Missing required key {e}")
        return False, f"Missing required key in test command: {e}", command
    except ValueError as e:
        logger.error(f"Validation failed: {e}")
        return False, str(e), command

def validate_test_values(command, testValues):
    try:
        data = command["data"]
        params = data["params"]

        chip_name = params["chipName"]
        test_name = params["testName"]

        chip_def = CHIP_TEST_DEFINITIONS[chip_name]
        chip_defaults = chip_def.get("default", {})
        chip_tests = chip_def.get("tests", {})
        test_def = chip_tests[test_name]

        # Merge default + test-specific schema
        expected_inputs = _merge_dict("inputs", chip_defaults, test_def)
        expected_outputs = _merge_dict("outputs", chip_defaults, test_def)

        # Extract units
        inputs_clean, inputs_units = _extract_units(testValues.get("inputs", {}))

        # Inputs: already validated
        inputs_clean, inputs_units = _extract_units(testValues.get("inputs", {}))
        for k in inputs_clean.keys():
            if k not in inputs_units or inputs_units[k] is None:
                # attach the unit from schema
                inputs_units[k] = expected_inputs.get(k, {}).get("unit")

        # Outputs: validate and correct units
        outputs_clean, outputs_units = _extract_units(testValues.get("outputs", {}))
        outputs_clean, outputs_units = _correct_units(outputs_clean, outputs_units, expected_outputs, "testValues.outputs", strict=False)
        # Apply defaults
        inputs_clean, inputs_units = _apply_defaults(expected_inputs, inputs_clean, "testValues.inputs", inputs_units)
        outputs_clean, outputs_units = _apply_defaults(expected_outputs, outputs_clean, "testValues.outputs", outputs_units)

        # Validate
        check_fields("testValues.inputs", inputs_clean, expected_inputs, inputs_units)
        check_fields("testValues.outputs", outputs_clean, expected_outputs, outputs_units)

        # Rebuild corrected testValues with units in the keys
        corrected_test_values = {
            "inputs": {f"{k}({inputs_units[k]})": v for k, v in inputs_clean.items()},
            "outputs": {f"{k}({outputs_units[k]})": v for k, v in outputs_clean.items()},
        }

        

        logger.info(f"testValues validation successful {corrected_test_values}")
        return True, "", corrected_test_values

    except KeyError as e:
        logger.error(f"testValues validation failed: Missing required key {e}")
        return False, f"Missing required key in testValues: {e}", testValues
    except ValueError as e:
        logger.error(f"testValues validation failed: {e}")
        return False, str(e), testValues

# ----------------- Helpers -----------------
def _merge_dict(field, defaults, overrides):
    """
    Merge default schema with test-specific schema.
    Rules:
    - If key exists in both → override with test-specific value
    - If key exists only in one → keep it
    Works recursively for dicts.
    """
    if field in ("inputs", "outputs"):
        base = defaults.get("testValues", {}).get(field, {}) if defaults else {}
        over = overrides.get("testValues", {}).get(field, {}) if overrides else {}
    else:
        base = defaults.get(field, {}) if defaults else {}
        over = overrides.get(field, {}) if overrides else {}

    def deep_merge(a, b):
        result = {}
        for k, v in a.items():
            result[k] = v.copy() if isinstance(v, dict) else v
        for k, v in b.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                # recursive merge
                result[k] = deep_merge(result[k], v)
            else:
                # override or add
                result[k] = v.copy() if isinstance(v, dict) else v
        return result

    return deep_merge(base, over)

def _extract_units(d: dict):
    clean = {}
    units = {}
    for key, value in d.items():
        m = re.match(r"^([a-zA-Z0-9_]+)\((.+)\)$", key)
        if m:
            clean_key = m.group(1)
            units[clean_key] = m.group(2)
        else:
            clean_key = key
            units[clean_key] = None
        clean[clean_key] = value
    return clean, units

def _apply_defaults(expected_schema, actual_dict, section_name="", actual_units=None):
    result = dict(actual_dict)
    units = dict(actual_units or {})
    for key, constraints in expected_schema.items():
        if key not in result and isinstance(constraints, dict) and "default" in constraints:
            default_val = constraints["default"]
            result[key] = default_val
            if "unit" in constraints and constraints["unit"]:
                units[key] = constraints["unit"]
            logger.info(f"{section_name}.{key} not provided → using default={default_val}")
    return result, units

import logging
import re
from .registryOfTests import CHIP_TEST_DEFINITIONS

logger = logging.getLogger("TestSchemaValidation")
logger.setLevel(logging.INFO)

# --- Unit conversion map ---
UNIT_CONVERSIONS = {
    ("pF", "nF"): lambda v: v / 1000,
    ("nF", "pF"): lambda v: v * 1000,
    ("uF", "nF"): lambda v: v * 1000,
    ("nF", "uF"): lambda v: v / 1000,
    ("mV", "V"): lambda v: v / 1000,
    ("V", "mV"): lambda v: v * 1000,
    ("A", "mA"): lambda v: v * 1000,
    ("mA", "A"): lambda v: v / 1000,
    ("kV/s", "V/s"): lambda v: v * 1000,
    ("V/s", "kV/s"): lambda v: v / 1000,
    ("°C", "C"): lambda v: v,
}

# ----------------- Main validate -----------------
def validate(command):
    try:
        data = command["data"]
        params = data["params"]

        chip_name = params["chipName"]
        test_name = params["testName"]
        test_config = params.get("testConfiguration", {})
        inputs = params.get("inputs", {})

        logger.info(f"Validating command for chip='{chip_name}', test='{test_name}'")

        if chip_name not in CHIP_TEST_DEFINITIONS:
            raise ValueError(f"Unsupported chip: {chip_name}")
        chip_def = CHIP_TEST_DEFINITIONS[chip_name]
        chip_defaults = chip_def.get("default", {})
        chip_tests = chip_def.get("tests", {})

        if test_name not in chip_tests:
            raise ValueError(f"Unsupported test '{test_name}' for chip '{chip_name}'")
        test_def = chip_tests[test_name]

        # Merge defaults + test-specific
        expected_config = _merge_dict("testConfiguration", chip_defaults, test_def)
        expected_inputs = _merge_dict("inputs", chip_defaults, test_def)

        # Extract values from message
        test_config_clean, config_units = _extract_units(test_config)
        inputs_clean, inputs_units = _extract_units(inputs)

        # Apply defaults when not defined
        test_config_clean, config_units = _apply_defaults(expected_config, test_config_clean, "testConfiguration", config_units)
        inputs_clean, inputs_units = _apply_defaults(expected_inputs, inputs_clean, "inputs", inputs_units)

        # Correct units
        test_config_clean, config_units = _correct_units(test_config_clean, config_units, expected_config, "testConfiguration")
        inputs_clean, inputs_units = _correct_units(inputs_clean, inputs_units, expected_inputs, "inputs", strict=True)

        # Validate
        check_fields("testConfiguration", test_config_clean, expected_config, config_units)
        check_fields("inputs", inputs_clean, expected_inputs, inputs_units)

        # Rebuild corrected command WITHOUT units in keys
        corrected_params = {
            "chipName": chip_name,
            "testName": test_name,
            "testConfiguration": {k: v for k, v in test_config_clean.items()},
            "inputs": {k: v for k, v in inputs_clean.items()}
        }

        corrected_command = {**command, "data": {**data, "params": corrected_params}}

        logger.info("Validation successful")
        return True, "", corrected_command

    except KeyError as e:
        logger.error(f"Validation failed: Missing required key {e}")
        return False, f"Missing required key in test command: {e}", command
    except ValueError as e:
        logger.error(f"Validation failed: {e}")
        return False, str(e), command

def validate_test_values(command, testValues):
    """
    Validates and reconstructs testValues.
    - Inputs: already checked, just attach units.
    - Outputs: convert units if possible, attach defaults if missing.
    """
    params = command["data"]["params"]
    chip_name = params["chipName"]
    test_name = params["testName"]

    chip_def = CHIP_TEST_DEFINITIONS[chip_name]
    chip_defaults = chip_def.get("default", {})
    test_def = chip_def.get("tests", {}).get(test_name, {})

    expected_inputs = _merge_dict("inputs", chip_defaults, test_def)
    expected_outputs = _merge_dict("outputs", chip_defaults, test_def)

    # Inputs: just attach units
    inputs_clean, inputs_units = _extract_units(testValues.get("inputs", {}))
    for k in inputs_clean:
        if inputs_units.get(k) is None:
            inputs_units[k] = expected_inputs.get(k, {}).get("unit")

    # Outputs: correct units (non-strict)
    outputs_clean, outputs_units = _extract_units(testValues.get("outputs", {}))
    outputs_clean, outputs_units = _correct_units(
        outputs_clean, outputs_units, expected_outputs, "testValues.outputs", strict=False
    )

    # Apply defaults for missing keys
    inputs_clean, inputs_units = _apply_defaults(expected_inputs, inputs_clean, "testValues.inputs", inputs_units)
    outputs_clean, outputs_units = _apply_defaults(expected_outputs, outputs_clean, "testValues.outputs", outputs_units)

    # Validate keys
    check_fields("testValues.inputs", inputs_clean, expected_inputs, inputs_units)
    check_fields("testValues.outputs", outputs_clean, expected_outputs, outputs_units)

    # Rebuild testValues with units in keys
    corrected_test_values = {
        "inputs": {f"{k}({inputs_units[k]})": v for k, v in inputs_clean.items()},
        "outputs": {f"{k}({outputs_units[k]})": v for k, v in outputs_clean.items()},
    }

    logger.info(f"testValues validation successful {corrected_test_values}")
    return True, "", corrected_test_values

# ----------------- Helpers -----------------
def _merge_dict(field, defaults, overrides):
    """
    Merge default schema with test-specific schema.
    Rules:
    - If key exists in both → override with test-specific value
    - If key exists only in one → keep it
    Works recursively for dicts.
    """
    if field in ("inputs", "outputs"):
        base = defaults.get("testValues", {}).get(field, {}) if defaults else {}
        over = overrides.get("testValues", {}).get(field, {}) if overrides else {}
    else:
        base = defaults.get(field, {}) if defaults else {}
        over = overrides.get(field, {}) if overrides else {}

    def deep_merge(a, b):
        result = {}
        for k, v in a.items():
            result[k] = v.copy() if isinstance(v, dict) else v
        for k, v in b.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                # recursive merge
                result[k] = deep_merge(result[k], v)
            else:
                # override or add
                result[k] = v.copy() if isinstance(v, dict) else v
        return result

    return deep_merge(base, over)

def _extract_units(d: dict):
    clean = {}
    units = {}
    for key, value in d.items():
        m = re.match(r"^([a-zA-Z0-9_]+)\((.+)\)$", key)
        if m:
            clean_key = m.group(1)
            units[clean_key] = m.group(2)
        else:
            clean_key = key
            units[clean_key] = None
        clean[clean_key] = value
    return clean, units

def _apply_defaults(expected_schema, actual_dict, section_name="", actual_units=None):
    result = dict(actual_dict)
    units = dict(actual_units or {})
    for key, constraints in expected_schema.items():
        if key not in result and isinstance(constraints, dict) and "default" in constraints:
            default_val = constraints["default"]
            result[key] = default_val
            if "unit" in constraints and constraints["unit"]:
                units[key] = constraints["unit"]
            logger.info(f"{section_name}.{key} not provided → using default={default_val}")
    return result, units

def _correct_units(clean_dict, unit_dict, expected_schema, section_name, strict=True):
    corrected = {}
    corrected_units = {}

    for key in clean_dict.keys():
        expected_unit = expected_schema.get(key, {}).get("unit")
        actual_unit = unit_dict.get(key)

        if expected_unit and (actual_unit is None):
            if strict:
                raise ValueError(f"{section_name}.{key}: missing unit, expected '{expected_unit}'")
            else:
                # Fill in unit if non-strict
                actual_unit = expected_unit
                unit_dict[key] = actual_unit

        if not expected_unit:
            corrected[key] = clean_dict[key]
            continue

        if actual_unit == expected_unit:
            corrected[key] = clean_dict[key]
            corrected_units[key] = expected_unit
        elif (actual_unit, expected_unit) in UNIT_CONVERSIONS:
            new_value = UNIT_CONVERSIONS[(actual_unit, expected_unit)](clean_dict[key])
            logger.info(f"{section_name}.{key}: converted {clean_dict[key]}{actual_unit} → {new_value}{expected_unit}")
            corrected[key] = new_value
            corrected_units[key] = expected_unit
        else:
            corrected[key] = clean_dict[key]
            corrected_units[key] = actual_unit

    return corrected, corrected_units

def check_fields(section_name, actual_dict, expected_schema, actual_units=None):
    actual_keys = set(actual_dict.keys())
    expected_keys = set(expected_schema.keys())

    missing = expected_keys - actual_keys
    extra = actual_keys - expected_keys

    if missing:
        raise ValueError(f"{section_name}: Missing fields: {missing}")
    if extra:
        raise ValueError(f"{section_name}: Unexpected fields: {extra}")

    for key, constraints in expected_schema.items():
        value = actual_dict.get(key)
        unit_in_msg = actual_units.get(key) if actual_units else None

        if constraints.get("unit") and unit_in_msg != constraints["unit"]:
            raise ValueError(f"{section_name}.{key}: unit '{unit_in_msg}' does not match expected '{constraints['unit']}'")

        if "enum" in constraints and value not in constraints["enum"]:
            raise ValueError(f"{section_name}.{key}: '{value}' not in allowed values {constraints['enum']}")

        if "min" in constraints and value is not None and float(value) < constraints["min"]:
            raise ValueError(f"{section_name}.{key}: '{value}' < min {constraints['min']}")
        if "max" in constraints and value is not None and float(value) > constraints["max"]:
            raise ValueError(f"{section_name}.{key}: '{value}' > max {constraints['max']}")

def check_fields(section_name, actual_dict, expected_schema, actual_units=None):
    actual_keys = set(actual_dict.keys())
    expected_keys = set(expected_schema.keys())

    missing = expected_keys - actual_keys
    extra = actual_keys - expected_keys

    if missing:
        raise ValueError(f"{section_name}: Missing fields: {missing}")
    if extra:
        raise ValueError(f"{section_name}: Unexpected fields: {extra}")

    for key, constraints in expected_schema.items():
        value = actual_dict.get(key)
        unit_in_msg = actual_units.get(key) if actual_units else None

        if constraints.get("unit") and unit_in_msg != constraints["unit"]:
            raise ValueError(f"{section_name}.{key}: unit '{unit_in_msg}' does not match expected '{constraints['unit']}'")

        if "enum" in constraints and value not in constraints["enum"]:
            raise ValueError(f"{section_name}.{key}: '{value}' not in allowed values {constraints['enum']}")

        if "min" in constraints and value is not None and float(value) < constraints["min"]:
            raise ValueError(f"{section_name}.{key}: '{value}' < min {constraints['min']}")
        if "max" in constraints and value is not None and float(value) > constraints["max"]:
            raise ValueError(f"{section_name}.{key}: '{value}' > max {constraints['max']}")