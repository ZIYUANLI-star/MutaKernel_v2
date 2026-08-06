#!/usr/bin/env python3
"""READ-ONLY live observation of running CSE workers.

- samples partial-snapshot res files (mtime + trial count) every ~6s;
- takes py-spy --nonblocking dumps (no process pause) of each worker.
Prints JSON. Runs ON THE REMOTE HOST.
"""
import glob
import json
import os
import subprocess
import time

DURATION_S = 150
POLL_S = 6
PYSPY = "/root/miniconda3/bin/py-spy"


def worker_pids():
    out = subprocess.run(
        ["pgrep", "-f", "_mutant_worker.py"], capture_output=True, text=True)
    return [int(p) for p in out.stdout.split()]


def snapshot_res():
    rows = []
    for path in glob.glob("/root/mk_v2_runs/e1/e1cse_*/res_*.json"):
        try:
            st = os.stat(path)
            with open(path) as fh:
                data = json.load(fh)
            trials = data.get("trials") or []
            last = trials[-1] if trials else {}
            rows.append({
                "res": os.path.basename(path),
                "mtime": st.st_mtime,
                "n_trials": len(trials),
                "sum_total_ms": round(sum(
                    (t.get("timings_ms") or {}).get("total_ms", 0)
                    for t in trials), 1),
                "last_round": {k: last.get(k) for k in
                               ("round_type", "round_index", "policy",
                                "sub_index", "status")},
            })
        except Exception as exc:
            rows.append({"res": path, "error": str(exc)[:120]})
    for path in glob.glob("/root/mk_v2_runs/e1/e1cse_*/cfg_*.json"):
        rows.append({"cfg": os.path.basename(path),
                     "mtime": os.stat(path).st_mtime})
    return rows


def pyspy_dump(pid):
    try:
        out = subprocess.run(
            [PYSPY, "dump", "--nonblocking", "--pid", str(pid)],
            capture_output=True, text=True, timeout=30)
        return out.stdout[-3000:] + ("\nERR:" + out.stderr[-500:]
                                     if out.returncode else "")
    except Exception as exc:
        return f"pyspy failed: {exc}"


def main():
    report = {"samples": [], "pyspy": []}
    t_end = time.time() + DURATION_S
    i = 0
    while time.time() < t_end:
        report["samples"].append({"t": time.time(), "res": snapshot_res()})
        if i % 4 == 1:
            for pid in worker_pids():
                report["pyspy"].append(
                    {"t": time.time(), "pid": pid, "dump": pyspy_dump(pid)})
        i += 1
        time.sleep(POLL_S)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
