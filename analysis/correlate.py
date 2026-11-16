
from loader import load_json


# Correlate measurements with network paths
def correlate_data(measurements, paths):

    correlated_results = []

    # Read every source-destination measurement
    for result in measurements["results"]:

        src = result["src"]
        dst = result["dst"]

        # Find the matching path
        for pair in paths["pairs"]:

            if pair["src"] == src and pair["dst"] == dst:

                active_path = pair["active_path"]

                # Convert path list into a string
                path_name = "-".join(active_path)

                # Get hop count
                hop_count = pair["hop_counts"][path_name]

                # Create correlated result
                record = {
                    "pair": f"{src}-{dst}",
                    "path": path_name,
                    "hop_count": hop_count,
                    "rtt_avg_ms": result["rtt_avg_ms"],
                    "jitter_ms": result["jitter_ms"],
                    "loss_pct": result["loss_pct"]
                }

                correlated_results.append(record)

    return correlated_results


# Display correlation results
def display_results(results):

    print("\nNETWORK PATH CORRELATION")
    print("-" * 85)

    print(
        f"{'Pair':<12}"
        f"{'Path':<18}"
        f"{'Hops':<8}"
        f"{'RTT(ms)':<12}"
        f"{'Jitter':<12}"
        f"{'Loss(%)':<10}"
    )

    print("-" * 85)

    for item in results:

        print(
            f"{item['pair']:<12}"
            f"{item['path']:<18}"
            f"{item['hop_count']:<8}"
            f"{item['rtt_avg_ms']:<12}"
            f"{item['jitter_ms']:<12}"
            f"{item['loss_pct']:<10}"
        )


# Main program
def main():

    paths = load_json("paths.json")

    measurement_files = [
        ("S0 BASELINE", "baseline_S0.json"),
        ("ADDITIONAL MEASUREMENT", "measurements.json")
    ]

    for label, filename in measurement_files:

        print(f"\n{label}")

        measurements = load_json(filename, mock=False)

        results = correlate_data(measurements, paths)

        if not results:
            print("No matching measurements and paths found.")
        else:
            display_results(results)


if __name__ == "__main__":
    main()
