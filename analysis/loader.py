
import json
import os
from pathlib import Path


# Find the project and selected data folder
PROJECT_DIR = Path(__file__).resolve().parent.parent

DATASET = os.getenv("SDN_DATASET", "mock")

if DATASET not in ("mock", "live"):
    raise ValueError("SDN_DATASET must be either 'mock' or 'live'")

DATA_FOLDER = PROJECT_DIR / "data" / DATASET


# Load JSON files safely
def load_json(filename, mock=True):

    if mock:
        filepath = DATA_FOLDER / filename
    else:
        filepath = PROJECT_DIR / "data" / filename


    # Check whether file exists
    if not filepath.is_file():
        raise FileNotFoundError(
            f"ERROR: File not found: {filepath}"
        )

    try:
        with open(filepath, "r", encoding="utf-8") as file:
            data = json.load(file)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"ERROR: Invalid JSON in {filename}: {error}"
        ) from error

    except OSError as error:
        raise OSError(
            f"ERROR: Cannot read {filename}: {error}"
        ) from error

    return data


# Check required fields
def check_fields(data, fields, filename):

    if not isinstance(data, dict):
        raise ValueError(f"{filename} must contain a JSON object")

    for field in fields:
        if field not in data:
            raise ValueError(
                f"{filename}: Missing required field '{field}'"
            )


# Validate measurements.json
def validate_measurements(data):

    check_fields(
        data,
        ["run_id", "results"],
        "measurements.json"
    )

    if not isinstance(data["results"], list):
        raise ValueError("Measurement results must be a list")

    required = [
        "src", "dst", "sent", "received", "loss_pct",
        "rtt_min_ms", "rtt_avg_ms", "rtt_max_ms",
        "jitter_ms", "probes"
    ]

    for result in data["results"]:

        check_fields(result, required, "measurement result")

        for field in ["src", "dst"]:
            if not isinstance(result[field], str):
                raise ValueError(f"{field} must be a string")

        for field in ["sent", "received"]:
            if type(result[field]) is not int or result[field] < 0:
                raise ValueError(f"{field} must be a non-negative integer")

        if result["received"] > result["sent"]:
            raise ValueError("Received probes cannot exceed sent probes")


        for field in [
            "loss_pct", "rtt_min_ms", "rtt_avg_ms",
            "rtt_max_ms", "jitter_ms"
        ]:
            value = result[field]

            if value is None and field in [
                "rtt_min_ms", "rtt_avg_ms",
                "rtt_max_ms", "jitter_ms"
            ]:
                continue

            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{field} must be numeric")

            if value < 0:
                raise ValueError(f"{field} cannot be negative")

        if not isinstance(result["probes"], list):
            raise ValueError("Probes must be a list")

        for probe in result["probes"]:

            check_fields(
                probe,
                ["seq", "rtt_ms", "lost", "timestamp"],
                "probe"
            )

            if type(probe["seq"]) is not int:
                raise ValueError("Probe sequence must be an integer")

            if not isinstance(probe["lost"], bool):
                raise ValueError("Probe lost must be true or false")

            if probe["rtt_ms"] is not None:
                if isinstance(probe["rtt_ms"], bool) or not isinstance(
                    probe["rtt_ms"], (int, float)
                ):
                    raise ValueError("Probe RTT must be numeric or null")

                if probe["rtt_ms"] < 0:
                    raise ValueError("Probe RTT cannot be negative")

            if isinstance(probe["timestamp"], bool) or not isinstance(
                probe["timestamp"], (int, float)
            ):
                raise ValueError("Probe timestamp must be numeric")

    return True


# Validate topology.json
def validate_topology(data):

    check_fields(
        data,
        ["switches", "hosts", "links"],
        "topology.json"
    )

    if not isinstance(data["switches"], list):
        raise ValueError("Switches must be a list")

    if not isinstance(data["hosts"], dict):
        raise ValueError("Hosts must be a dictionary")

    if not isinstance(data["links"], list):
        raise ValueError("Links must be a list")

    switches = data["switches"]

    for switch in switches:
        if not isinstance(switch, str):
            raise ValueError("Switch names must be strings")

    for host, switch in data["hosts"].items():
        if not isinstance(host, str) or switch not in switches:
            raise ValueError(
                f"Invalid host-to-switch mapping: {host} -> {switch}"
            )

    for link in data["links"]:
        if not isinstance(link, list) or len(link) != 2:
            raise ValueError("Each link must contain two switches")

        if any(switch not in switches for switch in link):
            raise ValueError(f"Link contains an unknown switch: {link}")

    return True


# Validate paths.json
def validate_paths(data):

    check_fields(data, ["pairs"], "paths.json")

    if not isinstance(data["pairs"], list):
        raise ValueError("Path pairs must be a list")

    for pair in data["pairs"]:

        check_fields(
            pair,
            [
                "src", "dst", "active_path",
                "alternative_paths", "hop_counts"
            ],
            "path pair"
        )

        if not isinstance(pair["src"], str):
            raise ValueError("Path source must be a string")

        if not isinstance(pair["dst"], str):
            raise ValueError("Path destination must be a string")

        if not isinstance(pair["active_path"], list):
            raise ValueError("Active path must be a list")

        if not isinstance(pair["alternative_paths"], list):
            raise ValueError("Alternative paths must be a list")

        if not isinstance(pair["hop_counts"], dict):
            raise ValueError("Hop counts must be a dictionary")

        all_paths = [pair["active_path"]] + pair["alternative_paths"]

        for path in all_paths:
            if not isinstance(path, list) or not path:
                raise ValueError("Every path must be a non-empty list")

            for switch in path:
                if not isinstance(switch, str):
                    raise ValueError("Path switch names must be strings")

        for path_name, count in pair["hop_counts"].items():
            if not isinstance(path_name, str):
                raise ValueError("Path names must be strings")

            if type(count) is not int or count < 0:
                raise ValueError("Hop counts must be non-negative integers")

    return True


# Main program
def main():

    measurements = load_json("measurements.json")
    topology = load_json("topology.json")
    paths = load_json("paths.json")

    validate_measurements(measurements)
    validate_topology(topology)
    validate_paths(paths)

    print("Measurements JSON: VALID")
    print("Topology JSON: VALID")
    print("Paths JSON: VALID")

    print("\nAll JSON files loaded and validated successfully!")

    print("Number of measurement results:",
          len(measurements["results"]))

    print("Number of switches:",
          len(topology["switches"]))

    print("Number of hosts:",
          len(topology["hosts"]))

    print("Number of network paths:",
          len(paths["pairs"]))


if __name__ == "__main__":

    try:
        main()

    except (FileNotFoundError, ValueError, OSError) as error:
        print(error)
