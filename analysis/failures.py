
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.loader import load_json
from config import (
    LOSS_DEGRADED_PCT,
    LOSS_FAILED_PCT,
    RTT_DEGRADED_FACTOR
)


def link_exists(link, topology):

    for current_link in topology["links"]:
        if set(link) == set(current_link):
            return True

    return False


def check_path_links(path, topology):

    missing_links = []

    for i in range(len(path) - 1):
        link = [path[i], path[i + 1]]

        if not link_exists(link, topology):
            missing_links.append(link)

    return missing_links


def detect_failures(measurements, topology, paths,
                    baseline_rtt_ms=None):

    failure_results = []

    for pair in paths["pairs"]:

        src = pair["src"]
        dst = pair["dst"]
        active_path = pair["active_path"]

        missing_links = check_path_links(
            active_path, topology
        )

        measurement = None

        for result in measurements["results"]:
            if result["src"] == src and result["dst"] == dst:
                measurement = result
                break

        status = "NORMAL"
        reasons = []

        if missing_links:
            status = "FAILED"
            reasons.append("Network link missing")

        elif measurement is None:
            status = "UNKNOWN"
            reasons.append("No matching measurement")

        else:
            loss = measurement["loss_pct"]
            rtt = measurement["rtt_avg_ms"]
            received = measurement["received"]

            if received == 0 or loss > LOSS_FAILED_PCT:
                status = "FAILED"
                reasons.append("High packet loss")

            elif loss > LOSS_DEGRADED_PCT:
                status = "DEGRADED"
                reasons.append("Packet loss above threshold")

            if (
                baseline_rtt_ms is not None
                and baseline_rtt_ms > 0
                and rtt > baseline_rtt_ms * RTT_DEGRADED_FACTOR
            ):
                if status != "FAILED":
                    status = "DEGRADED"

                reasons.append("RTT above threshold")

        failure_results.append({
            "src": src,
            "dst": dst,
            "path": active_path,
            "status": status,
            "missing_links": missing_links,
            "reasons": reasons
        })

    return failure_results


def display_failures(results):

    print("\nNETWORK FAILURE ANALYSIS")
    print("-" * 60)

    for result in results:

        print(
            f"{result['src']} -> {result['dst']}"
        )

        print("Active path:", " -> ".join(result["path"]))
        print("Status:", result["status"])

        if result["missing_links"]:
            print("Missing links:", result["missing_links"])

        if result["reasons"]:
            print("Reason:", ", ".join(result["reasons"]))

        print("-" * 60)


def main():

    topology = load_json("topology.json")
    paths = load_json("paths.json")

    measurement_files = [
        ("S0 BASELINE", "baseline_S0.json"),
        ("ADDITIONAL MEASUREMENT", "measurements.json")
    ]

    for label, filename in measurement_files:

        print(f"\n{label}")

        measurements = load_json(filename, mock=False)

        results = detect_failures(
            measurements,
            topology,
            paths
        )

        display_failures(results)
if __name__ == "__main__":

    try:
        main()

    except (FileNotFoundError, ValueError, OSError) as error:
        print("ERROR:", error)
