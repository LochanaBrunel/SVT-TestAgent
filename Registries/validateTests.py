import logging
import re
from .registryOfTests import CHIP_TEST_DEFINITIONS

logger = logging.getLogger("TestSchemaValidation")
logger.setLevel(logging.INFO)


def validate(command):
    try:
        data = command["data"]
        params = data["params"]

        chip_name = params["chipName"]
        test_name = params["testName"]
        test_config = params.get("TestConfiguration", {})
        inputs = params.get("inputs", {})

        logger.info(f"Validating command for chip='{chip_name}', test='{test_name}'")

        if chip_name not in CHIP_TEST_DEFINITIONS:
            raise ValueError(f"Unsupported chip: {chip_name}")
        chip_def = CHIP_TEST_DEFINITIONS[chip_name]
        chip_defaults = chip_def.get("default", {})
        chip_tests = chip_def.get("Tests", {})

        if test_name not in chip_tests:
            raise ValueError(f"Unsupported test '{test_name}' for chip '{chip_name}'")
        test_def = chip_tests[test_name]

        expected_config = _merge_dict("TestConfiguration", chip_defaults, test_def)
        expected_inputs = _merge_dict("inputs", chip_defaults.get("testValues", {}), test_def.get("testValues", {}))

        logger.info(f"Expected TestConfiguration keys: {set(expected_config.keys())}")
        logger.info(f"Expected inputs keys: {set(expected_inputs.keys())}")

        # Strip units from keys, but keep units for validation
        test_config_clean, config_units = _extract_units(test_config)
        inputs_clean, inputs_units = _extract_units(inputs)

        check_fields("TestConfiguration", test_config_clean, expected_config, config_units)
        check_fields("inputs", inputs_clean, expected_inputs, inputs_units)

        logger.info("Validation successful ✅")
        return True, ""

    except KeyError as e:
        logger.error(f"Validation failed: Missing required key {e}")
        return False, f"Missing required key in test command: {e}"
    except ValueError as e:
        logger.error(f"Validation failed: {e}")
        return False, str(e)


def validate_test_values(test_values, chip_name, test_name):
    try:
        logger.info(f"Validating testValues for chip='{chip_name}', test='{test_name}'")

        if chip_name not in CHIP_TEST_DEFINITIONS:
            return False, f"Unknown chip: {chip_name}"

        chip_def = CHIP_TEST_DEFINITIONS[chip_name]
        chip_defaults = chip_def.get("default", {})
        chip_tests = chip_def.get("Tests", {})

        if test_name not in chip_tests:
            return False, f"Unknown test '{test_name}' for chip '{chip_name}'"

        test_def = chip_tests[test_name]
        expected_tv_inputs = _merge_dict("inputs", chip_defaults.get("testValues", {}), test_def.get("testValues", {}))
        expected_tv_outputs = _merge_dict("outputs", chip_defaults.get("testValues", {}), test_def.get("testValues", {}))

        tv_inputs_clean, tv_inputs_units = _extract_units(test_values.get("inputs", {}))
        tv_outputs_clean, tv_outputs_units = _extract_units(test_values.get("outputs", {}))

        check_fields("testValues.inputs", tv_inputs_clean, expected_tv_inputs, tv_inputs_units)
        check_fields("testValues.outputs", tv_outputs_clean, expected_tv_outputs, tv_outputs_units)

        logger.info("testValues validation successful ✅")
        return True, ""

    except KeyError as e:
        logger.error(f"Validation failed: Missing key {e}")
        return False, f"Missing key in testValues: {e}"
    except ValueError as e:
        logger.error(f"Validation failed: {e}")
        return False, str(e)


def _merge_dict(field, defaults, overrides):
    """
    Merge the schema dict for a specific field.
    - `field` can be 'TestConfiguration', 'inputs', or 'outputs'
    - Only keys relevant to that field are returned.
    """
    merged = {}

    # Handle defaults
    if defaults and isinstance(defaults, dict):
        if field == "inputs" or field == "outputs":
            merged.update(defaults.get("testValues", {}).get(field, {}))
        else:
            merged.update(defaults.get(field, {}))

    # Handle overrides (test-specific)
    if overrides and isinstance(overrides, dict):
        if field == "inputs" or field == "outputs":
            merged.update(overrides.get("testValues", {}).get(field, {}))
        else:
            merged.update(overrides.get(field, {}))

    return merged


def _extract_units(d: dict):
    """
    Returns two dictionaries:
    - cleaned keys without units
    - dict mapping cleaned keys to the units found in the message (or None)
    """
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


def check_fields(section_name, actual_dict, expected_schema, actual_units=None):
    """
    Validate actual_dict against expected_schema keys and constraints.
    Also validate units if actual_units are provided.
    """
    actual_keys = set(actual_dict.keys())
    expected_keys = set(expected_schema.keys())

    missing = expected_keys - actual_keys
    extra = actual_keys - expected_keys

    logger.debug(f"Checking section '{section_name}': actual={actual_keys}, expected={expected_keys}")

    if missing:
        raise ValueError(f"{section_name}: Missing fields: {missing}")
    if extra:
        raise ValueError(f"{section_name}: Unexpected fields: {extra}")

    for key, constraints in expected_schema.items():
        value = actual_dict.get(key)
        unit_in_msg = actual_units.get(key) if actual_units else None

        # Check unit matches registry
        if constraints and isinstance(constraints, dict) and "unit" in constraints:
            expected_unit = constraints["unit"]
            if unit_in_msg and unit_in_msg != expected_unit:
                raise ValueError(f"{section_name}.{key}: unit '{unit_in_msg}' does not match expected '{expected_unit}'")

        # Enum check
        if constraints and isinstance(constraints, dict) and "enum" in constraints:
            if value not in constraints["enum"]:
                raise ValueError(f"{section_name}.{key}: '{value}' not in allowed values {constraints['enum']}")

        # Min/max check
        if constraints and isinstance(constraints, dict):
            if "min" in constraints and value is not None:
                if float(value) < constraints["min"]:
                    raise ValueError(f"{section_name}.{key}: '{value}' < min {constraints['min']}")
            if "max" in constraints and value is not None:
                if float(value) > constraints["max"]:
                    raise ValueError(f"{section_name}.{key}: '{value}' > max {constraints['max']}")