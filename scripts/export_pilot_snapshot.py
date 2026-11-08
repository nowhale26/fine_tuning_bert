"""Export a timestamped, small snapshot of a running or finished pilot."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

ROOT = Path(__file__).resolve().parents[1]


def export(attempt):
    folder = ROOT / "results" / "pilot" / attempt
    metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    target = folder / "snapshots" / now.strftime("%Y%m%dT%H%M%SZ")
    target.mkdir(parents=True, exist_ok=False)
    source = ROOT / "results" / "pilot" / "outputs" / "logs" / (attempt + "_seed" + str(metadata["seed"]))
    all_steps = []
    latest_eval = None
    for name in ("train_results.tsv", "eval_results.tsv"):
        path = source / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            fields = reader.fieldnames
            rows = [r for r in reader if fields and all(r.get(k) is not None for k in fields) and r.get("global_step", "").lstrip("-").isdigit()]
        if not fields:
            continue
        with (target / name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
        all_steps.extend(int(r["global_step"]) for r in rows if int(r["global_step"]) >= 0)
        if name == "eval_results.tsv" and rows:
            latest_eval = rows[-1]
    stderr = ROOT / "results" / "pilot" / (attempt + ".stderr.log")
    text = stderr.read_text(encoding="utf-8", errors="replace")
    total = re.search(r"Total optimization steps\s*=\s*(\d+)", text)
    metadata.update({"snapshot_at_utc": now.isoformat(), "last_logged_step": max(all_steps, default=0),
                     "planned_total_steps": int(total.group(1)) if total else None,
                     "latest_evaluation": latest_eval,
                     "is_completed_run": metadata["status"] == "completed"})
    (target / "snapshot.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    lines = ["# Pilot snapshot", "", "- Taken at UTC: " + now.isoformat(),
             "- Run status at snapshot: " + metadata["status"],
             "- Last logged step: " + str(metadata["last_logged_step"]),
             "- Planned total steps: " + str(metadata["planned_total_steps"]),
             "- Latest dev evaluation: " + str(latest_eval), "",
             "This records only observations available at the stated time. It is not a multi-seed result.", ""]
    (target / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(str(target), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", default="original-seed0")
    parser.add_argument("--at", help="Optional ISO8601 timestamp with timezone for a deferred snapshot.")
    args = parser.parse_args()
    if args.at:
        when = datetime.fromisoformat(args.at)
        if when.tzinfo is None:
            parser.error("--at must include a timezone")
        while True:
            remaining = (when - datetime.now(timezone.utc)).total_seconds()
            if remaining <= 0:
                break
            time.sleep(min(30, remaining))
    export(args.attempt)
