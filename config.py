"""
SDN Network Diagnostic and Path Analysis Tool
Central project configuration
"""

# ==============================
# Controller Configuration
# ==============================

CONTROLLER_IP = "127.0.0.1"
CONTROLLER_OF_PORT = 6653
CONTROLLER_PORT = CONTROLLER_OF_PORT

REST_PORT = 8080
CONTROLLER_REST = f"http://10.0.0.254:{REST_PORT}"


# ==============================
# OpenFlow Configuration
# ==============================

OPENFLOW_VERSION = 0x04  # OpenFlow 1.3


# ==============================
# Topology Configuration
# ==============================

HOSTS = {
    "h1": "10.0.0.1",
    "h2": "10.0.0.2",
    "h3": "10.0.0.3",
    "h4": "10.0.0.4",
}

HOST_SWITCH = {
    "h1": "s1",
    "h2": "s4",
    "h3": "s2",
    "h4": "s3",
}

SWITCHES = ["s1", "s2", "s3", "s4"]


# ==============================
# Switch-to-switch Links
# ==============================

# Format: (source, destination, delay_ms)

SWITCH_LINKS = [
    ("s1", "s2", 5),
    ("s2", "s4", 5),
    ("s1", "s3", 20),
    ("s3", "s4", 20),
]


# ==============================
# Probe Settings
# ==============================

ECHO_PORT = 9999
PROBES_PER_DEST = 100
PROBE_TIMEOUT_S = 1.0
PROBE_INTERVAL_S = 0.2

REPORT_EVERY_N_PROBES = 10
PROBE_REPORT_INTERVAL = REPORT_EVERY_N_PROBES


# ==============================
# Network Performance Thresholds
# ==============================

LOSS_DEGRADED_PCT = 5
LOSS_FAILED_PCT = 50
RTT_DEGRADED_FACTOR = 2

# Alternative naming conventions

DEGRADED_LOSS_PERCENT = LOSS_DEGRADED_PCT
FAILED_LOSS_PERCENT = LOSS_FAILED_PCT
RTT_DEGRADED_MULTIPLIER = RTT_DEGRADED_FACTOR


# ==============================
# Diagnostic Reporting
# ==============================

DATA_DIR = "data"


# ==============================
# Default and Alternative Paths
# ==============================

DEFAULT_PATH = ["s1", "s2", "s4"]

ALTERNATIVE_PATH = ["s1", "s3", "s4"]
