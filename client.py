"""
UDP Network Diagnostic Probe Client
SDN Network Diagnostic and Path Analysis Tool

Sends UDP probes to destination hosts, measures RTT,
packet loss and jitter, and periodically reports results
to the SDN controller.
"""

import argparse
import json
import os
import sys
import socket
import time
import uuid
from datetime import datetime

import requests

# Add the project root to Python's import path.
sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from config import (
    HOSTS,
    ECHO_PORT,
    PROBES_PER_DEST,
    PROBE_TIMEOUT_S,
    PROBE_INTERVAL_S,
    REPORT_EVERY_N_PROBES,
    LOSS_DEGRADED_PCT,
    LOSS_FAILED_PCT,
    RTT_DEGRADED_FACTOR,
    CONTROLLER_REST,
)


PROJECT_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

MEASUREMENTS_FILE = os.path.join(
    PROJECT_DIR,
    "data",
    "measurements.json"
)


def calculate_metrics(probes):
    """Calculate packet loss, RTT statistics and jitter."""

    sent = len(probes)

    successful_rtts = [
        probe["rtt_ms"]
        for probe in probes
        if not probe["lost"]
    ]

    received = len(successful_rtts)
    lost = sent - received

    loss_pct = (lost / sent * 100) if sent else 0.0

    if successful_rtts:
        rtt_min = min(successful_rtts)
        rtt_avg = sum(successful_rtts) / received
        rtt_max = max(successful_rtts)

        differences = [
            abs(successful_rtts[i] - successful_rtts[i - 1])
            for i in range(1, received)
        ]

        jitter = (
            sum(differences) / len(differences)
            if differences else 0.0
        )

    else:
        rtt_min = None
        rtt_avg = None
        rtt_max = None
        jitter = None

    return {
        "sent": sent,
        "received": received,
        "lost": lost,
        "loss_pct": round(loss_pct, 2),
        "rtt_min_ms": round(rtt_min, 3) if rtt_min is not None else None,
        "rtt_avg_ms": round(rtt_avg, 3) if rtt_avg is not None else None,
        "rtt_max_ms": round(rtt_max, 3) if rtt_max is not None else None,
        "jitter_ms": round(jitter, 3) if jitter is not None else None,
    }


def classify_status(metrics, baseline_rtt):
    """Classify a measurement window as ok, degraded or failed."""

    if metrics["loss_pct"] >= LOSS_FAILED_PCT:
        return "failed"

    if metrics["loss_pct"] >= LOSS_DEGRADED_PCT:
        return "degraded"

    current_rtt = metrics["rtt_avg_ms"]

    if (
        baseline_rtt is not None
        and current_rtt is not None
        and current_rtt > baseline_rtt * RTT_DEGRADED_FACTOR
    ):
        return "degraded"

    return "ok"


def send_report(src, dst, metrics, status):
    """Send a measurement window to the controller REST API."""

    report = {
        "src": src,
        "dst": dst,
        "loss_pct": metrics["loss_pct"],
        "rtt_avg_ms": metrics["rtt_avg_ms"],
        "status": status,
        "timestamp": time.time(),
        "sent": metrics["sent"],
        "received": metrics["received"],
    }

    try:
        response = requests.post(
            f"{CONTROLLER_REST}/diag/report",
            json=report,
            timeout=2
        )

        if response.ok:
            print(
                f"[REPORT] {src} -> {dst}: "
                f"{response.json()}"
            )
        else:
            print(
                f"[REPORT WARNING] Controller returned "
                f"HTTP {response.status_code}. "
                f"Continuing probes."
            )

    except requests.RequestException as error:
        print(
            f"[REPORT WARNING] Controller unavailable: {error}. "
            f"Continuing probes."
        )


def probe_destination(src, dst, run_id):
    """Probe one destination host."""

    destination_ip = HOSTS[dst]

    print("\n" + "=" * 60)
    print(f"Starting UDP probes: {src} -> {dst}")
    print(f"Destination IP: {destination_ip}")
    print(f"Number of probes: {PROBES_PER_DEST}")
    print("=" * 60)

    all_probes = []
    window_probes = []
    baseline_rtt = None

    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    )

    sock.settimeout(PROBE_TIMEOUT_S)

    try:
        for seq in range(1, PROBES_PER_DEST + 1):

            timestamp = time.time()

            message = {
                "seq": seq,
                "ts_send": timestamp,
                "src": src,
                "dst": dst,
            }

            payload = json.dumps(message).encode("utf-8")

            start = time.perf_counter()

            probe_result = {
                "seq": seq,
                "rtt_ms": None,
                "lost": True,
                "timestamp": timestamp,
            }

            try:
                sock.sendto(
                    payload,
                    (destination_ip, ECHO_PORT)
                )

                response_data, _ = sock.recvfrom(2048)

                end = time.perf_counter()

                response = json.loads(
                    response_data.decode("utf-8")
                )

                # Accept only the reply corresponding to this probe.
                if (
                    response.get("seq") == seq
                    and response.get("src") == src
                    and response.get("dst") == dst
                ):
                    rtt_ms = (end - start) * 1000

                    probe_result["rtt_ms"] = round(rtt_ms, 3)
                    probe_result["lost"] = False

                    print(
                        f"[RECEIVED] {src} -> {dst} "
                        f"| Seq: {seq} "
                        f"| RTT: {rtt_ms:.3f} ms"
                    )

                else:
                    print(
                        f"[INVALID REPLY] {src} -> {dst} "
                        f"| Seq: {seq}"
                    )

            except socket.timeout:
                print(
                    f"[TIMEOUT] {src} -> {dst} "
                    f"| Seq: {seq}"
                )

            except (json.JSONDecodeError, UnicodeDecodeError):
                print(
                    f"[INVALID REPLY] Malformed response "
                    f"| Seq: {seq}"
                )

            except OSError as error:
                print(
                    f"[SOCKET ERROR] Probe {seq}: {error}"
                )

            all_probes.append(probe_result)
            window_probes.append(probe_result)

            # Report after each complete measurement window.
            if (
                len(window_probes) == REPORT_EVERY_N_PROBES
                or seq == PROBES_PER_DEST
            ):
                metrics = calculate_metrics(window_probes)

                if (
                    baseline_rtt is None
                    and metrics["rtt_avg_ms"] is not None
                ):
                    baseline_rtt = metrics["rtt_avg_ms"]

                status = classify_status(
                    metrics,
                    baseline_rtt
                )

                print("\n[WINDOW SUMMARY]")
                print(
                    f"Probes: {metrics['sent']} | "
                    f"Received: {metrics['received']} | "
                    f"Lost: {metrics['lost']}"
                )
                print(f"Packet loss: {metrics['loss_pct']}%")
                print(f"Average RTT: {metrics['rtt_avg_ms']} ms")
                print(f"Jitter: {metrics['jitter_ms']} ms")
                print(f"Status: {status}")

                send_report(
                    src,
                    dst,
                    metrics,
                    status
                )

                window_probes = []

            if seq < PROBES_PER_DEST:
                time.sleep(PROBE_INTERVAL_S)

    finally:
        sock.close()

    final_metrics = calculate_metrics(all_probes)

    print("\n[DESTINATION COMPLETE]")
    print(f"Route tested: {src} -> {dst}")
    print(f"Total probes: {final_metrics['sent']}")
    print(f"Received: {final_metrics['received']}")
    print(f"Lost: {final_metrics['lost']}")
    print(f"Packet loss: {final_metrics['loss_pct']}%")
    print(f"Average RTT: {final_metrics['rtt_avg_ms']} ms")
    print(f"Jitter: {final_metrics['jitter_ms']} ms")

    return {
        "src": src,
        "dst": dst,
        **final_metrics,
        "probes": all_probes,
    }


def save_measurements(run_id, results):
    """Save all destination measurements as JSON."""

    os.makedirs(
        os.path.dirname(MEASUREMENTS_FILE),
        exist_ok=True
    )

    output = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }

    with open(MEASUREMENTS_FILE, "w") as file:
        json.dump(output, file, indent=4)

    print(
        f"\n[FILE SAVED] Measurements written to:\n"
        f"{MEASUREMENTS_FILE}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="UDP network diagnostic probe client"
    )

    parser.add_argument(
        "--src",
        required=True,
        choices=list(HOSTS.keys()),
        help="Source Mininet host"
    )

    parser.add_argument(
        "--dst",
        required=True,
        nargs="+",
        choices=list(HOSTS.keys()),
        help="One or more destination Mininet hosts"
    )

    args = parser.parse_args()

    if args.src in args.dst:
        parser.error("Source and destination cannot be the same host.")

    run_id = f"run_{uuid.uuid4().hex[:8]}"

    print(f"Diagnostic run ID: {run_id}")
    print(f"Source host: {args.src}")
    print(f"Destinations: {', '.join(args.dst)}")

    results = []

    for dst in args.dst:
        result = probe_destination(
            args.src,
            dst,
            run_id
        )
        results.append(result)

    save_measurements(run_id, results)


if __name__ == "__main__":
    main()
