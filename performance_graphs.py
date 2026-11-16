import json
from pathlib import Path
import matplotlib.pyplot as plt

# Load actual project measurements
baseline = json.loads(Path("data/baseline_S0.json").read_text())["results"][0]
additional = json.loads(Path("data/measurements.json").read_text())["results"][0]

scenarios = ["S0 Baseline", "Additional Measurement"]

metrics = [
    ("rtt_avg_ms", "Average RTT", "Milliseconds", "average_rtt_comparison.png"),
    ("jitter_ms", "Jitter", "Milliseconds", "jitter_comparison.png"),
    ("loss_pct", "Packet Loss", "Percentage (%)", "packet_loss_comparison.png"),
]

Path("results").mkdir(exist_ok=True)

for field, title, ylabel, filename in metrics:
    values = [baseline[field], additional[field]]

    plt.figure(figsize=(8, 5))
    bars = plt.bar(scenarios, values)
    plt.title(title + " Comparison")
    plt.ylabel(ylabel)
    plt.grid(axis="y", linestyle="--", alpha=0.4)

    for bar, value in zip(bars, values):
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{value:.3f}",
            ha="center",
            va="bottom"
        )

    plt.tight_layout()
    plt.savefig(Path("results") / filename, dpi=300)
    plt.close()

print("All three performance graphs created successfully.")
print("Saved in the results/ folder:")
for _, _, _, filename in metrics:
    print(" -", filename)
