CHIP_TEST_DEFINITIONS = {
    "SLDO": {
        "default": {
            "TestConfiguration": {
                "mode": {"unit": None ,"enum": [0, 1] },
                "loadCapacitance": {"unit": "nF","enum": [10, 100, 1000, 10000] },
                "loadCurrent": {"unit": "mA", "enum": [40, 500, 900]},
                "temperature": {"unit": "C", "min": -20, "max": 125},
            },
            "testValues": {
                "inputs": {
                    "vInTarget": {"unit": "V", "min": 0, "max": 1.55},
                    "iInLimit": {"unit": "A",  "min": 0, "max": 1.5},
                    "rampRate": {"unit": "kV/s", "default": 3.1},
                },
                "outputs": {
                    "v_out": {"unit": "V", "max": 10},
                }
            }
        },
        "Tests": {
            "PowerRampUp": {
                "TestConfiguration": {},
                "testValues": {}
            },
            "PSRR": {
                "testValues": {
                    "inputs": {
                        "Signal_amplitude": {"unit": "V"},
                        "Signal_frequency": {"unit": "Hz"},
                    },
                    "outputs": {
                        "PSRR": {"unit": "dB"}
                    }
                }
            }
        }
    }
}