# TestAgent/Registries/validateTests.py
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Tuple

from .registryOfTests import CHIP_TEST_DEFINITIONS

logger = logging.getLogger("TestSchemaValidation")
logger.setLevel(logging.INFO)

JsonDict = Dict[str, Any]

# ---------------------------------------------------------------------------
# Unit conversion map (from_unit, to_unit) → callable
# Extend as needed.
# ---------------------------------------------------------------------------
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
    ("°C", "C"): lambda v: v,   # alias (no conversion)
}

# Regex: split keys of form "name(unit)" → ("name", "unit")
KEY_WITH_UNIT = re.compile(r"^([a-zA-Z0-9_]+)\((.+)\)$")


# =============================================================================
# Public API
# =============================================================================
def validate(command: JsonDict) -> Tuple[bool, str, JsonDict]:
    """
    Validate an incoming RunTest-style command (schema from registryOfTests).

    Expected envelope:
    {
        "command": "RunTest",
        "data": {
            "params": {
                "chipName": "SLDO",
                "testName": "PowerRampUp",
                "testConfiguration": {...},   # optional/may be empty
                "inputs": {...}               # required per schema
            }
        },
        "testId": ...
    }

    Returns:
        (is_valid, error_message, corrected_command)

        - corrected_command: same structure as input `command`, but with:
            * defaults applied
            * units normalized (e.g. inputs.vInTarget(mV) -> V with converted value)
            * keys stripped of "(unit)" in params/testConfiguration/inputs
    """
    try:
        data = command["data"]
        params = data["params"]

        chip_name = params["chipName"]
        test_name = params["testName"]
        test_config = params.get("testConfiguration", {}) or {}
        inputs = params.get("inputs", {}) or {}

        logger.info("Validating command for chip='%s', test='%s'", chip_name, test_name)

        # ---- Registry lookups
        if chip_name not in CHIP_TEST_DEFINITIONS:
            raise ValueError(f"Unsupported chip: {chip_name}")

        chip_def = CHIP_TEST_DEFINITIONS[chip_name]
        chip_defaults = chip_def.get("default", {})
        chip_tests = chip_def.get("tests", {})

        if test_name not in chip_tests:
            raise ValueError(f"Unsupported test '{test_name}' for chip '{chip_name}'")

        test_def = chip_tests[test_name]

        # ---- Expected (merged) schema
        expected_config = _merge_schema("testConfiguration", chip_defaults, test_def)
        expected_inputs = _merge_schema("inputs", chip_defaults, test_def)

        # ---- Extract and normalize units from input
        test_config_clean, config_units = _extract_units(test_config)
        inputs_clean, inputs_units = _extract_units(inputs)

        # ---- Apply defaults where missing
        test_config_clean, config_units = _apply_defaults(
            expected_config, test_config_clean, section_name="testConfiguration", actual_units=config_units
        )
        inputs_clean, inputs_units = _apply_defaults(
            expected_inputs, inputs_clean, section_name="inputs", actual_units=inputs_units
        )

        # ---- Coerce units to expected schema
        test_config_clean, config_units = _coerce_units(
            test_config_clean, config_units, expected_config, section_name="testConfiguration", strict=False
        )
        inputs_clean, inputs_units = _coerce_units(
            inputs_clean, inputs_units, expected_inputs, section_name="inputs", strict=True
        )

        # ---- Final field checks (enums, min/max, units match)
        _check_fields("testConfiguration", test_config_clean, expected_config, config_units)
        _check_fields("inputs", inputs_clean, expected_inputs, inputs_units)

        # ---- Rebuild corrected command (no units in keys)
        corrected_params = {
            "chipName": chip_name,
            "testName": test_name,
            "testConfiguration": dict(test_config_clean),
            "inputs": dict(inputs_clean),
        }
        corrected_command = {**command, "data": {**data, "params": corrected_params}}

        logger.info("Validation successful")
        return True, "", corrected_command

    except KeyError as e:
        msg = f"Missing required key in test command: {e}"
        logger.error("Validation failed: %s", msg)
        return False, msg, command
    except ValueError as e:
        msg = str(e)
        logger.error("Validation failed: %s", msg)
        return False, msg, command


def validate_test_values(command: JsonDict, test_values: JsonDict) -> Tuple[bool, str, JsonDict]:
    """
    Validate and normalize testValues returned by the test system.

    `command` must be a validated command (as from validate()) or at least contain:
        command["data"]["params"]["chipName"]
        command["data"]["params"]["testName"]

    test_values format:
        {
          "inputs":  {...},     # may contain unit-suffixed keys
          "outputs": {...}      # may contain unit-suffixed keys
        }

    Returns:
        (is_valid, error_message, corrected_test_values)

        corrected_test_values contains units explicitly in keys, e.g.
            {
              "inputs":  {"vInTarget(V)": 1.55, ...},
              "outputs": {"vOut(V)": 1.3, ...}
            }
    """
    try:
        params = command["data"]["params"]
        chip_name = params["chipName"]
        test_name = params["testName"]

        chip_def = CHIP_TEST_DEFINITIONS[chip_name]
        chip_defaults = chip_def.get("default", {})
        test_def = chip_def.get("tests", {}).get(test_name, {})

        expected_inputs = _merge_schema("inputs", chip_defaults, test_def)
        expected_outputs = _merge_schema("outputs", chip_defaults, test_def)

        # ---- Inputs: Attach expected unit if missing
        inputs_clean, inputs_units = _extract_units(test_values.get("inputs", {}) or {})
        for k in inputs_clean:
            inputs_units[k] = inputs_units.get(k) or expected_inputs.get(k, {}).get("unit")

        # ---- Outputs: Coerce units (non-strict; fill missing units from schema)
        outputs_clean, outputs_units = _extract_units(test_values.get("outputs", {}) or {})
        outputs_clean, outputs_units = _coerce_units(
            outputs_clean, outputs_units, expected_outputs, section_name="testValues.outputs", strict=False
        )

        # ---- Apply defaults for missing keys
        inputs_clean, inputs_units = _apply_defaults(
            expected_inputs, inputs_clean, section_name="testValues.inputs", actual_units=inputs_units
        )
        outputs_clean, outputs_units = _apply_defaults(
            expected_outputs, outputs_clean, section_name="testValues.outputs", actual_units=outputs_units
        )

        # ---- Final field checks
        _check_fields("testValues.inputs", inputs_clean, expected_inputs, inputs_units)
        _check_fields("testValues.outputs", outputs_clean, expected_outputs, outputs_units)

        # ---- Rebuild with units in keys
        corrected_test_values = {
            "inputs": {f"{k}({inputs_units[k]})": v for k, v in inputs_clean.items()},
            "outputs": {f"{k}({outputs_units[k]})": v for k, v in outputs_clean.items()},
        }

        logger.info("testValues validation successful %s", corrected_test_values)
        return True, "", corrected_test_values

    except KeyError as e:
        msg = f"Missing required key in testValues: {e}"
        logger.error("testValues validation failed: %s", msg)
        return False, msg, test_values
    except ValueError as e:
        msg = str(e)
        logger.error("testValues validation failed: %s", msg)
        return False, msg, test_values


# =============================================================================
# Helpers
# =============================================================================
def _merge_schema(field: str, defaults: JsonDict, overrides: JsonDict) -> JsonDict:
    """
    Merge default schema with test-specific schema.
      - For "inputs"/"outputs", pick from defaults["testValues"][field] and overrides["testValues"][field].
      - For others (e.g., "testConfiguration"), pick directly.
    rules:
      - in both → test-specific overrides default
      - missing → keep what exists
    recursive for nested dicts
    """
    if field in ("inputs", "outputs"):
        base = (defaults.get("testValues", {}) or {}).get(field, {}) if defaults else {}
        over = (overrides.get("testValues", {}) or {}).get(field, {}) if overrides else {}
    else:
        base = defaults.get(field, {}) if defaults else {}
        over = overrides.get(field, {}) if overrides else {}

    def deep_merge(a: JsonDict, b: JsonDict) -> JsonDict:
        out: JsonDict = {}
        for k, v in a.items():
            out[k] = v.copy() if isinstance(v, dict) else v
        for k, v in b.items():
            if k in out and isinstance(out[k], dict) and isinstance(v, dict):
                out[k] = deep_merge(out[k], v)
            else:
                out[k] = v.copy() if isinstance(v, dict) else v
        return out

    return deep_merge(base, over)


def _extract_units(d: JsonDict) -> Tuple[JsonDict, JsonDict]:
    """
    Split "key(unit)" → "key" + unit mapping.
    If no unit suffix, unit is None.
    """
    clean: JsonDict = {}
    units: JsonDict = {}
    for key, value in (d or {}).items():
        m = KEY_WITH_UNIT.match(str(key))
        if m:
            clean_key = m.group(1)
            units[clean_key] = m.group(2)
        else:
            clean_key = key
            units[clean_key] = None
        clean[clean_key] = value
    return clean, units


def _apply_defaults(expected_schema: JsonDict, actual_dict: JsonDict, section_name: str = "", actual_units: JsonDict | None = None) -> Tuple[JsonDict, JsonDict]:
    """
    For any key present in schema with "default", apply it if missing in actual.
    Also set the unit if schema provides one.
    """
    result = dict(actual_dict or {})
    units = dict(actual_units or {})

    for key, constraints in (expected_schema or {}).items():
        if key not in result and isinstance(constraints, dict) and "default" in constraints:
            default_val = constraints["default"]
            result[key] = default_val
            if "unit" in constraints and constraints["unit"]:
                units[key] = constraints["unit"]
            logger.info("%s.%s not provided → using default=%s", section_name, key, default_val)

    return result, units


def _coerce_units(clean_dict: JsonDict, unit_dict: JsonDict, expected_schema: JsonDict, section_name: str, strict: bool = True) -> Tuple[JsonDict, JsonDict]:
    """
    Coerce values in `clean_dict` to units from `expected_schema` using `UNIT_CONVERSIONS`.
    - strict=True  → missing units cause errors if expected specifies a unit.
    - strict=False → will fill in missing units from schema and convert if possible.
    """
    corrected: JsonDict = {}
    corrected_units: JsonDict = {}

    for key, value in (clean_dict or {}).items():
        expected_unit = (expected_schema.get(key) or {}).get("unit")
        actual_unit = (unit_dict or {}).get(key)

        if expected_unit and (actual_unit is None):
            if strict:
                raise ValueError(f"{section_name}.{key}: missing unit, expected '{expected_unit}'")
            else:
                # fill from schema
                actual_unit = expected_unit

        # No unit declared in schema → pass-through
        if not expected_unit:
            corrected[key] = value
            continue

        if actual_unit == expected_unit:
            corrected[key] = value
            corrected_units[key] = expected_unit
            continue

        # Try conversion
        conv = UNIT_CONVERSIONS.get((actual_unit, expected_unit))
        if conv is not None:
            try:
                new_val = conv(value)
            except Exception:
                raise ValueError(f"{section_name}.{key}: cannot convert {value} from '{actual_unit}' to '{expected_unit}'")
            logger.info("%s.%s: converted %s%s → %s%s", section_name, key, value, actual_unit, new_val, expected_unit)
            corrected[key] = new_val
            corrected_units[key] = expected_unit
        else:
            # No known conversion — keep unchanged but record actual unit
            corrected[key] = value
            corrected_units[key] = actual_unit

    return corrected, corrected_units


def _check_fields(section_name: str, actual_dict: JsonDict, expected_schema: JsonDict, actual_units: JsonDict | None = None) -> None:
    """
    Check:
      - All expected keys are present (and no extra keys exist).
      - Units (if specified) match expected.
      - Values respect enum / min / max constraints.
    """
    actual_keys = set((actual_dict or {}).keys())
    expected_keys = set((expected_schema or {}).keys())

    missing = expected_keys - actual_keys
    extra = actual_keys - expected_keys

    if missing:
        raise ValueError(f"{section_name}: Missing fields: {sorted(missing)}")
    if extra:
        raise ValueError(f"{section_name}: Unexpected fields: {sorted(extra)}")

    units = actual_units or {}
    for key, constraints in (expected_schema or {}).items():
        value = actual_dict.get(key)
        expected_unit = constraints.get("unit")
        unit_in_msg = units.get(key) if isinstance(units, dict) else None

        # Unit check (when specified in schema)
        if expected_unit and unit_in_msg is not None and unit_in_msg != expected_unit:
            raise ValueError(f"{section_name}.{key}: unit '{unit_in_msg}' does not match expected '{expected_unit}'")

        # Enum constraint
        if "enum" in constraints and value not in constraints["enum"]:
            raise ValueError(f"{section_name}.{key}: '{value}' not in allowed values {constraints['enum']}")

        # Range constraints
        if "min" in constraints and value is not None and float(value) < constraints["min"]:
            raise ValueError(f"{section_name}.{key}: '{value}' < min {constraints['min']}")
        if "max" in constraints and value is not None and float(value) > constraints["max"]:
            raise ValueError(f"{section_name}.{key}: '{value}' > max {constraints['max']}")