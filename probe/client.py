import argparse
import json
import os
import socket
import statistics
import sys
import time

# Let the script find config.py in the repo root, wherever it is run from
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (HOSTS, ECHO_PORT, PROBES_PER_DEST, PROBE_TIMEOUT_S,
                    PROBE_INTERVAL_S, DATA_DIR)


IP_TO_NAME = {ip: name for name, ip in HOSTS.items()}


def resolve(x):
    """Accept a host name (h2) or an IP (10.0.0.2).
    Mininet's CLI replaces h2 with its IP before running the command."""
    if x in HOSTS:
        return x
    if x in IP_TO_NAME:
        return IP_TO_NAME[x]
    raise SystemExit(f"Unknown host: {x}")


def probe_destination(src, dst, count, timeout, interval):
    """Send `count` UDP probes to dst and measure RTT and loss."""
    ip = HOSTS[dst]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    probes = []
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
                if reply.get("seq") == seq:      # ignore late replies to old probes
                    rtt_ms = round((time.time() - t_send) * 1000, 3)
                    lost = False
                    break
        except socket.timeout:
            pass
        except OSError as e:
            print(f"[WARN] send/receive error to {dst}: {e}")
        probes.append({"seq": seq, "rtt_ms": rtt_ms, "lost": lost,
                       "timestamp": round(t_send, 3)})
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
    ap.add_argument("--out", default=os.path.join(DATA_DIR, "measurements.json"))
    args = ap.parse_args()
    args.src = resolve(args.src)
    args.dst = [resolve(d) for d in args.dst]

    results = []
    for dst in args.dst:
        print(f"Probing {dst} ({HOSTS[dst]}) with {args.count} probes...")
        probes = probe_destination(args.src, dst, args.count,
                                   PROBE_TIMEOUT_S, PROBE_INTERVAL_S)
        r = summarise(args.src, dst, probes)
        results.append(r)
        print(f"  {args.src} -> {dst}: sent={r['sent']} received={r['received']} "
              f"loss={r['loss_pct']}%  rtt min/avg/max = "
              f"{r['rtt_min_ms']}/{r['rtt_avg_ms']}/{r['rtt_max_ms']} ms  "
              f"jitter={r['jitter_ms']} ms")

    out = {"run_id": f"run_{int(time.time())}", "scenario": args.scenario,
           "mode": args.mode, "results": results}
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Saved results to {args.out}")


if __name__ == "__main__":
    main()
