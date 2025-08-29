CHIP_TEST_DEFINITIONS = {
    "SLDO": {
        "default": {
            "TestConfiguration": {
                "mode", "loadCapacitance", "loadCurrent", "temperature"
            },
            "testValues": {
                "inputs": {"vInTarget", "iInLimit", "rampRate"},  
                "outputs": {"v_out(V)"}
            }
        },
        "Tests": {
            "PowerRampUp": {
                "testValues": {
                    "inputs": set(),
                    "outputs": set()
                }
            },
            "PSRR": {
                "testValues": {
                    "inputs": {"Signal_amplitude", "Signal_frequency"},
                    "outputs": {"PSRR"}
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