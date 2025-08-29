CHIP_TEST_DEFINITIONS = {
    "SLDO": {
        "default": {
            "TestConfiguration": {
                "mode", "loadCapacitance", "loadCurrent", "temperature"
            },
            "testValues": {
                "inputs": set(),   # can be empty if only test-specific
                "outputs": set()
            }
        },
        "Tests": {
            "PowerRampUp": {
                "inputs": {"vInTarget", "iInLimit", "rampRate"},
                "testValues": {
                    "inputs": {"vInTarget", "iInLimit", "rampRate"},
                    "outputs": {"v_out(V)"}
                }
            },
            "PSRR": {
                "inputs": {"vInTarget", "loadCurrent"},
                "testValues": {
                    "inputs": {"vInTarget", "loadCurrent"},
                    "outputs": {"dropoutVoltage"}
                }
            }
        }
    },

    "NVG": {
        "default": {
            "TestConfiguration": {
                "loadCapacitance", "loadCurrent", "temperature"
            },
            "testValues": {
                "inputs": set(),
                "outputs": set()
            }
        },
        "Tests": {
            "TransientTest": {
                "inputs": {"vInTarget", "iInLimit", "rampRate"},
                "testValues": {
                    "inputs": {"vInTarget", "iInLimit", "rampRate"},
                    "outputs": {"v_out"}
                }
            }
        }
    }
}