#!/usr/bin/env python3
"""Parallel pre-warmer for per-subject torch extension caches.

Walks the subject manifest and, for every subject whose per-subject cache
namespace has no built .so yet, imports the candidate module in a low-priority
subprocess so torch.utils.cpp_extension compiles it into exactly the cache
directory the FSE runner will later use (same namespace derivation, GPU kept
visible so the nvcc arch flags are byte-identical to the runner's).

Compilation artifacts are content-addressed byte-identical outputs; verdict
semantics are untouched.  torch's build-directory file lock (baton) makes a
concurrent runner/prewarmer race safe: one side builds, the other waits then
reuses.  Every attempt is appended to prewarm_log.jsonl for the audit trail.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MK = Path("/root/mk_v2")
PYBIN = "/root/miniconda3/bin/python"

sys.path.insert(0, str(MK))
from src.experiments.manifest import stable_json_sha256  # noqa: E402

IMPORT_SNIPPET = r"""
import importlib.util, sys
path = sys.argv[1]
spec = importlib.util.spec_from_file_location("prewarm_candidate", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print("PREWARM_IMPORT_OK")
"""


def namespace_for(subject_sha256: str) -> str:
    return stable_json_sha256({"cache_namespace": subject_sha256})[:16]


def has_built_so(ns_dir: Path) -> bool:
    return ns_dir.is_dir() and any(ns_dir.rglob("*.so"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", required=True, type=Path)
    ap.add_argument("--run-dir", required=True, type=Path,
                    help="the lane output dir that owns torch_extensions/")
    ap.add_argument("--artifact-root", default="/", type=Path)
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()

    manifest = json.loads(args.subjects.read_text(encoding="utf-8"))
    subjects = manifest["subjects"]
    ext_root = args.run_dir / "torch_extensions"
    home = args.run_dir / "worker_home"
    log_path = args.run_dir / "prewarm_log.jsonl"

    pending = []
    for s in subjects:
        ns = namespace_for(s["subject_sha256"])
        if not has_built_so(ext_root / ns):
            cand = args.artifact_root / s["candidate"]["logical_path"]
            pending.append((s["subject_id"], ns, cand))
    print(f"subjects={len(subjects)} pending_prewarm={len(pending)} "
          f"jobs={args.jobs}", flush=True)

    def append_log(rec: dict) -> None:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")

    def work(item):
        subject_id, ns, cand = item
        ns_dir = ext_root / ns
        ns_dir.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env.update({
            "HOME": str(home),
            "TORCH_EXTENSIONS_DIR": str(ns_dir),
            "CUDA_CACHE_PATH": str(args.run_dir / "cuda_cache" / ns),
            "PYTHONUNBUFFERED": "1",
        })
        started = time.time()
        rec = {"subject_id": subject_id, "namespace": ns,
               "candidate": str(cand), "started_at": started}
        try:
            proc = subprocess.run(
                ["nice", "-n", "15", PYBIN, "-c", IMPORT_SNIPPET, str(cand)],
                env=env, cwd=str(MK), capture_output=True, text=True,
                timeout=args.timeout)
            ok = proc.returncode == 0 and "PREWARM_IMPORT_OK" in proc.stdout
            rec["status"] = "ok" if ok else "import_error"
            if not ok:
                rec["tail"] = (proc.stdout + proc.stderr)[-500:]
        except subprocess.TimeoutExpired:
            rec["status"] = "timeout"
        except Exception as exc:  # noqa: BLE001
            rec["status"] = "driver_error"
            rec["tail"] = f"{type(exc).__name__}: {exc}"[:300]
        rec["wall_s"] = round(time.time() - started, 1)
        rec["built_so"] = has_built_so(ns_dir)
        append_log(rec)
        print(f"{subject_id}: {rec['status']} so={rec['built_so']} "
              f"{rec['wall_s']}s", flush=True)
        return rec["status"] == "ok"

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(work, pending))
    print(f"prewarm done: ok={sum(results)}/{len(results)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
