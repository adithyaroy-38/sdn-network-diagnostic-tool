import argparse
import json
import os
import socket
import statistics
import sys
import time

import requests

# Let the script find config.py in the repo root, wherever it is run from
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (HOSTS, ECHO_PORT, PROBES_PER_DEST, PROBE_TIMEOUT_S,
                    PROBE_INTERVAL_S, DATA_DIR, CONTROLLER_REST,
                    REPORT_EVERY_N_PROBES, LOSS_DEGRADED_PCT,
                    LOSS_FAILED_PCT, RTT_DEGRADED_FACTOR)

IP_TO_NAME = {ip: name for name, ip in HOSTS.items()}


def resolve(x):
    """Accept a host name (h2) or an IP (10.0.0.2).
    Mininet's CLI replaces h2 with its IP before running the command."""
    if x in HOSTS:
        return x
    if x in IP_TO_NAME:
        return IP_TO_NAME[x]
    raise SystemExit(f"Unknown host: {x}")


def classify(window, baseline_rtt):
    """Label a window of probes ok / degraded / failed using the shared thresholds."""
    rtts = [p["rtt_ms"] for p in window if not p["lost"]]
    loss = (len(window) - len(rtts)) / len(window) * 100
    avg = statistics.mean(rtts) if rtts else None
    if not rtts or loss >= LOSS_FAILED_PCT:
        status = "failed"
    elif loss > LOSS_DEGRADED_PCT:
        status = "degraded"
    elif baseline_rtt and avg > RTT_DEGRADED_FACTOR * baseline_rtt:
        status = "degraded"
    else:
        status = "ok"
    return status, round(loss, 2), (round(avg, 3) if avg is not None else None)


def send_report(controller, src, dst, status, loss, avg):
    """POST /diag/report to the controller. Never crashes the probing."""
    body = {"src": src, "dst": dst, "loss_pct": loss, "rtt_avg_ms": avg,
            "status": status, "timestamp": round(time.time(), 3)}
    try:
        r = requests.post(controller.rstrip("/") + "/diag/report", json=body, timeout=2)
        resp = r.json()
        return resp if isinstance(resp, dict) else {"action": "invalid"}
    except (requests.RequestException, ValueError) as e:
        print(f"    [WARN] could not report to controller: {e}")
        return {"action": "unreachable"}


def probe_destination(src, dst, count, timeout, interval, controller, reports):
    """Send `count` UDP probes to dst; report to the controller every N probes."""
    ip = HOSTS[dst]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    probes = []
    baseline = None
    for seq in range(1, count + 1):
        t_send = time.time()
        payload = json.dumps({"seq": seq, "ts_send": t_send,
                              "src": src, "dst": dst}).encode()
        rtt_ms, lost = None, True
        try:
            sock.sendto(payload, (ip, ECHO_PORT))
            deadline = t_send + timeout
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise socket.timeout
                sock.settimeout(remaining)
                data, _ = sock.recvfrom(2048)
                try:
                    reply = json.loads(data.decode())
                except ValueError:
                    continue
                if isinstance(reply, dict) and reply.get("seq") == seq:
                    rtt_ms = round((time.time() - t_send) * 1000, 3)
                    lost = False
                    break
        except socket.timeout:
            pass
        except OSError as e:
            print(f"[WARN] send/receive error to {dst}: {e}")
        probes.append({"seq": seq, "rtt_ms": rtt_ms, "lost": lost,
                       "timestamp": round(t_send, 3)})

        if controller and len(probes) % REPORT_EVERY_N_PROBES == 0:
            window = probes[-REPORT_EVERY_N_PROBES:]
            status, loss, avg = classify(window, baseline)
            if avg is not None and (baseline is None or avg < baseline):
                baseline = avg
            resp = send_report(controller, src, dst, status, loss, avg)
            reports.append({"dst": dst, "after_seq": seq, "status": status,
                            "loss_pct": loss, "rtt_avg_ms": avg,
                            "controller_response": resp,
                            "timestamp": round(time.time(), 3)})
            print(f"    probes {seq - REPORT_EVERY_N_PROBES + 1}-{seq}: {status} "
                  f"(loss {loss}%) -> controller: {resp.get('action')}")
        time.sleep(interval)
    sock.close()
    return probes


def summarise(src, dst, probes):
    rtts = [p["rtt_ms"] for p in probes if not p["lost"]]
    sent, received = len(probes), len(rtts)
    diffs = [abs(a - b) for a, b in zip(rtts, rtts[1:])]
    return {
        "src": src, "dst": dst,
        "sent": sent, "received": received,
        "loss_pct": round((sent - received) / sent * 100, 2) if sent else 0.0,
        "rtt_min_ms": round(min(rtts), 3) if rtts else None,
        "rtt_avg_ms": round(statistics.mean(rtts), 3) if rtts else None,
        "rtt_max_ms": round(max(rtts), 3) if rtts else None,
        "jitter_ms": round(statistics.mean(diffs), 3) if diffs else 0.0,
        "probes": probes,
    }


def main():
    ap = argparse.ArgumentParser(description="UDP probe client")
    ap.add_argument("--src", required=True, help="this host, e.g. h1")
    ap.add_argument("--dst", required=True, nargs="+", help="destination hosts, e.g. h2 h3")
    ap.add_argument("--count", type=int, default=PROBES_PER_DEST)
    ap.add_argument("--scenario", default="S0")
    ap.add_argument("--mode", default="unknown", help="static or dynamic")
    ap.add_argument("--controller", default=CONTROLLER_REST, help="controller REST URL")
    ap.add_argument("--no-report", action="store_true", help="do not report to the controller")
    ap.add_argument("--out", default=os.path.join(DATA_DIR, "measurements.json"))
    args = ap.parse_args()
    args.src = resolve(args.src)
    args.dst = [resolve(d) for d in args.dst]
    controller = None if args.no_report else args.controller

    results, reports = [], []
    for dst in args.dst:
        print(f"Probing {dst} ({HOSTS[dst]}) with {args.count} probes...")
        probes = probe_destination(args.src, dst, args.count, PROBE_TIMEOUT_S,
                                   PROBE_INTERVAL_S, controller, reports)
        r = summarise(args.src, dst, probes)
        results.append(r)
        print(f"  {args.src} -> {dst}: sent={r['sent']} received={r['received']} "
              f"loss={r['loss_pct']}%  rtt min/avg/max = "
              f"{r['rtt_min_ms']}/{r['rtt_avg_ms']}/{r['rtt_max_ms']} ms  "
              f"jitter={r['jitter_ms']} ms")

    out = {"run_id": f"run_{int(time.time())}", "scenario": args.scenario,
           "mode": args.mode, "results": results, "reports": reports}
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Saved results to {args.out}")


if __name__ == "__main__":
    main()
