# Topology
HOSTS = {"h1": "10.0.0.1", "h2": "10.0.0.2", "h3": "10.0.0.3", "h4": "10.0.0.4"}
SWITCHES = ["s1", "s2", "s3", "s4"]
# Host-to-switch mapping
HOST_SWITCH = {
    "h1": "s1",
    "h2": "s4",
    "h3": "s2",
    "h4": "s3"
}

# Switch-to-switch links and delays (milliseconds)
SWITCH_LINKS = [
    ("s1", "s2", 5),
    ("s2", "s4", 5),
    ("s1", "s3", 20),
    ("s3", "s4", 20)
]
# Probe settings
ECHO_PORT = 9999
PROBES_PER_DEST = 100
PROBE_TIMEOUT_S = 1.0
PROBE_INTERVAL_S = 0.2
REPORT_EVERY_N_PROBES = 10

# Controller
CONTROLLER_IP = "127.0.0.1"
CONTROLLER_OF_PORT = 6653
CONTROLLER_REST = "http://127.0.0.1:8080"

# Thresholds
LOSS_DEGRADED_PCT = 5
LOSS_FAILED_PCT = 50
RTT_DEGRADED_FACTOR = 2

DATA_DIR = "data"
