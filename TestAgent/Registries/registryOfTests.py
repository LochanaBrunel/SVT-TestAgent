CHIP_TEST_DEFINITIONS = {
    "SLDO": {
        "default": {
            "testConfiguration": {
                "mode": {"unit": None, "enum": [0, 1]},
                "loadCapacitance": {"unit": "nF", "enum": [10, 100, 1000, 10000]},
                "loadCurrent": {"unit": "mA", "enum": [40, 500, 900]},
                "temperature": {"unit": "C", "min": -20, "max": 125},
            },
            "testValues": {
                "inputs": {
                    "vInTarget": {"unit": "V", "min": 0, "max": 1.55},
                    "iInLimit": {"unit": "A", "min": 0, "max": 1.5},
                    "rampRate": {"unit": "kV/s", "default": 3.1},
                },
                "outputs": {
                    "vOut": {"unit": "V"},
                }
            }
        },
        "tests": {
            "PowerRampUp": {
                "testConfiguration": {},
                "testValues": {}
            },
            "PSRR": {
                "testConfiguration": {},
                "testValues": {
                    "inputs": {
                        "signalAmplitude": {"unit": "mV"},
                        "signalFrequency": {"unit": "Hz"},
                    },
                    "outputs": {
                        "psrr": {"unit": "dB"}
                    }
                }
            },
            "PowerRampRate": {
                "testConfiguration": {},
                "testValues": {},
            },
            "DACScan": {
                "testConfiguration": {},
                "testValues": {
                    "inputs": {
                        "dacCode": {"unit": None, "enum": list(range(31))},
                    },
                    "outputs": {
                        "vOut": {"unit": "V", "values": 31}
                    }
                }
            },
            "OverCurrent": {
                "testConfiguration": {},
                "testValues": {
                    "inputs": {
                        "iExcess": {"unit": "A"},
                    },
                    "outputs": {
                        "iOut": {"unit": "A"},
                        "iIn": {"unit": "A"},
                    }
                }
            },
            "Irradiation": {
                "testConfiguration": {},
                "testValues": {
                    "inputs": {
                        "irradiationDose": {"unit": "rad"},
                    },
                    "outputs": {
                        "iOut": {"unit": "A"},
                        "iIn": {"unit": "A"},
                    }
                }
            }
        }
    },
    "NVG": {
        "default": { # Placeholder values — adapt to NVG requirements
            "testConfiguration": {
                "configOne": {"unit": None, "enum": [0, 1, 2]},
                "configTwo": {"unit": "µA", "enum": [10, 50, 100]},
            },
            "testValues": {
                "inputs": {
                    "vSupply": {"unit": "V", "min": 0, "max": 5},
                    "iSupply": {"unit": "mA", "min": 0, "max": 200},
                },
                "outputs": {
                    "vOut": {"unit": "V", "min": 0, "max": 5},
                }
            }
        },
        "tests": {
            "testOne": {
                "testConfiguration": {},
                "testValues": {}
            },
            "testTwo": {
                "testConfiguration": {},
                "testValues": {}
            }
        }
    }
}