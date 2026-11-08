"""Run the read-only upstream implementation and record one pilot attempt.

Only adaptation in this launcher: short output directory names on Windows.
Training, optimizer, data processing and checkpoint selection remain upstream.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    upstream = args.upstream.resolve()
    config = args.config.resolve()
    os.chdir(ROOT)
    for path in (str(upstream), str(upstream / "src")):
        sys.path.insert(0, path)
    os.environ.setdefault("WANDB_MODE", "offline")
    import torch
    import transformers

    if args.check_only:
        print(json.dumps({"python": sys.version, "torch": torch.__version__,
                          "transformers": transformers.__version__,
                          "transformers_path": transformers.__file__,
                          "cuda_available": torch.cuda.is_available(),
                          "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}, indent=2))
        importlib.import_module("examples.bert_stable_fine_tuning.run_finetuning")
        print("Upstream training imports: OK", flush=True)
        return

    destination = ROOT / "results" / "pilot" / args.attempt
    destination.mkdir(parents=True, exist_ok=False)
    info = {
        "status": "running", "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(), "seed": args.seed, "upstream": str(upstream),
        "config": str(config), "config_sha256": sha256(config),
        "launcher_sha256": sha256(__file__), "python": sys.version,
        "platform": platform.platform(), "torch": torch.__version__,
        "transformers": transformers.__version__, "transformers_path": transformers.__file__,
        "cuda_runtime": torch.version.cuda, "cudnn": torch.backends.cudnn.version(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "adaptations": ["Portable Python 3.8 / PyTorch 1.13.1 environment", "Local data and weight paths", "Short output directory names via launcher; no training algorithm changes"],
        "data_sha256": {name: sha256(ROOT / "data" / "RTE" / name) for name in ("train.tsv", "dev.tsv")},
    }
    try:
        info["upstream_sha"] = subprocess.check_output(
            ["git", "-c", "safe.directory=" + upstream.as_posix(), "-C", str(upstream), "rev-parse", "HEAD"],
            text=True).strip()
    except Exception as exc:
        info["upstream_sha_error"] = str(exc)
    metadata = destination / "metadata.json"
    metadata.write_text(json.dumps(info, indent=2), encoding="utf-8")
    started = time.perf_counter()
    exit_code = 1
    try:
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable; refusing to start a CPU training run.")
        torch.cuda.reset_peak_memory_stats()
        module = importlib.import_module("examples.bert_stable_fine_tuning.run_finetuning")

        def short_unique_dir(path, config, original_args, timestamp):
            output = Path(path) / (args.attempt + "_seed" + str(original_args.seed))
            output.mkdir(parents=True, exist_ok=False)
            return str(output)

        module.create_unique_dir = short_unique_dir
        sys.argv = [str(upstream / "examples/bert_stable_fine_tuning/run_finetuning.py"),
                    "--config", str(config), "--do_train", "--do_eval", "--seed", str(args.seed)]
        print("PILOT_METADATA " + json.dumps(info), flush=True)
        module.main()
        info["status"] = "completed"
        exit_code = 0
    except BaseException:
        info["status"] = "failed"
        info["traceback"] = traceback.format_exc()
        print(info["traceback"], file=sys.stderr, flush=True)
    finally:
        info["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        info["elapsed_seconds"] = time.perf_counter() - started
        info["exit_code"] = exit_code
        if torch.cuda.is_available():
            info["peak_allocated_bytes"] = torch.cuda.max_memory_allocated()
            info["peak_reserved_bytes"] = torch.cuda.max_memory_reserved()
        metadata.write_text(json.dumps(info, indent=2), encoding="utf-8")
        print("PILOT_FINISHED " + json.dumps(info), flush=True)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
