"""Print progress from the pilot's existing logs without touching training."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def duration(seconds):
    minutes = int(max(0, seconds) // 60)
    return "{}h {:02d}m".format(minutes // 60, minutes % 60)


def read_tsv(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    return [row for row in rows if row.get("global_step", "").lstrip("-").isdigit()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", default="original-seed0")
    args = parser.parse_args()
    metadata = ROOT / "results" / "pilot" / args.attempt / "metadata.json"
    info = json.loads(metadata.read_text(encoding="utf-8"))
    logs = ROOT / "results" / "pilot" / "outputs" / "logs" / (args.attempt + "_seed" + str(info["seed"]))
    stderr = ROOT / "results" / "pilot" / (args.attempt + ".stderr.log")
    text = stderr.read_text(encoding="utf-8", errors="replace") if stderr.exists() else ""
    match = re.search(r"Total optimization steps\s*=\s*(\d+)", text)
    total = int(match.group(1)) if match else None
    train = read_tsv(logs / "train_results.tsv")
    evaluation = read_tsv(logs / "eval_results.tsv")
    steps = [int(row["global_step"]) for row in train + evaluation if int(row["global_step"]) >= 0]
    current = max(steps, default=0)
    if info["status"] == "completed" and total is not None:
        current = total
    started = datetime.fromisoformat(info["started_at_utc"])
    finished = datetime.fromisoformat(info["finished_at_utc"]) if "finished_at_utc" in info else datetime.now(timezone.utc)
    elapsed = (finished - started).total_seconds()
    print("Status: {} | GPU: {} | PID: {}".format(info["status"], info.get("gpu"), info["pid"]))
    if total:
        print("Logged step: {}/{} ({:.1f}% of the whole run)".format(current, total, 100 * current / total))
        epochs = re.search(r"Num Epochs\s*=\s*(\d+)", text)
        if epochs:
            count = int(epochs.group(1))
            print("Completed epoch equivalents: {:.2f}/{}".format(current * count / total, count))
    print("Elapsed: " + duration(elapsed))
    if info["status"] == "running" and current > 0 and total:
        print("Approx. remaining: " + duration(elapsed * (total - current) / current))
    if evaluation:
        latest = evaluation[-1]
        print("Latest dev accuracy: {} at logged step {} (not a multi-seed result)".format(latest.get("acc", "n/a"), latest["global_step"]))
    if train:
        print("Latest logged train loss: {}".format(train[-1].get("loss", "n/a")))
    print("Training progress logs every 10 steps; ETA includes loading and evaluation overhead.")


if __name__ == "__main__":
    main()
