"""Collect an attempt's metadata, checkpoints and dev metrics into a small report."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import time

ROOT = Path(__file__).resolve().parents[1]


def summarize(attempt):
    directory = ROOT / "results" / "pilot" / attempt
    info = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    logs = ROOT / "results" / "pilot" / "outputs" / "logs" / (attempt + "_seed0")
    if info["status"] != "running":
        for name in ("train_results.tsv", "eval_results.tsv"):
            source = logs / name
            if source.exists():
                shutil.copyfile(source, directory / name)
    files = sorted(str(p.relative_to(ROOT)) for p in logs.rglob("*") if p.is_file())
    eval_texts = {}
    for path in logs.rglob("*eval*results*"):
        if path.is_file():
            eval_texts[str(path.relative_to(ROOT))] = path.read_text(encoding="utf-8", errors="replace")
    result = {"collected_at_utc": datetime.now(timezone.utc).isoformat(),
              "metadata": info, "log_files": files, "eval_outputs": eval_texts}
    (directory / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = ["# Pilot: " + attempt, "", "- Status: " + info["status"],
             "- GPU: " + str(info.get("gpu")), "- Upstream SHA: " + str(info.get("upstream_sha")),
             "- Seed: " + str(info["seed"]), "- Time, seconds: " + str(info.get("elapsed_seconds", "pending")),
             "- Peak CUDA allocated, bytes: " + str(info.get("peak_allocated_bytes", "pending")), "",
             "This is one pilot seed, not a reproduction over multiple seeds.", ""]
    for name, content in eval_texts.items():
        lines += ["## " + name, "", "```text", content, "```", ""]
    if info.get("traceback"):
        lines += ["## Failure", "", "```text", info["traceback"], "```", ""]
    (directory / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": info["status"], "report": str(directory / "summary.md")}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()
    metadata = ROOT / "results" / "pilot" / args.attempt / "metadata.json"
    while args.wait:
        info = json.loads(metadata.read_text(encoding="utf-8"))
        if info["status"] != "running":
            break
        import psutil
        if not psutil.pid_exists(info["pid"]):
            raise RuntimeError("Pilot process disappeared without a final metadata record; inspect stderr.")
        time.sleep(10)
    summarize(args.attempt)
