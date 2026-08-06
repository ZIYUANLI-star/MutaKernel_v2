#!/usr/bin/env python3
"""Read-only resume preconditions for the B9 calibration rerun.

Deployed to /root/mk_v2/_b9_precheck.py.  Verifies that the critical path is
finished, that the torch.quantile fix is actually the code on disk, and that
the memory budget is available.  Exits non-zero if any hard check fails; never
kills anything and never touches the GPU.

Process detection walks /proc and excludes this process and its ancestors, so
it cannot be fooled by (or interfere with) the shell command line that invoked
it -- the reason `pkill -f` is banned in this campaign.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

MK = Path("/root/mk_v2")
OUT_ROOT = Path("/root/mk_v2_runs/e3_b9_calib")
B9_SRC = MK / "src/experiments/external_ports/b9_seeded_fuzzing.py"
PAUSE_MARKER = OUT_ROOT / "PAUSED_FOR_SIGNOFF_RERUN"
CRITICAL_PATH_NEEDLE = "_mutant_worker.py"
GIB = float(1 << 30)

failures: list[str] = []
warnings: list[str] = []


def ok(label, detail=""):
    print("  [ok]   %s %s" % (label, detail))


def fail(label, detail=""):
    print("  [FAIL] %s %s" % (label, detail))
    failures.append(f"{label} {detail}".strip())


def warn(label, detail=""):
    print("  [warn] %s %s" % (label, detail))
    warnings.append(f"{label} {detail}".strip())


def _ppid(pid):
    try:
        for line in open(f"/proc/{pid}/status", encoding="utf-8"):
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except OSError:
        pass
    return 0


def find_processes(needle):
    """Processes whose command line contains ``needle``, minus self/ancestors."""
    excluded = set()
    pid = os.getpid()
    while pid and pid != 1:
        excluded.add(pid)
        pid = _ppid(pid)
    hits = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid in excluded:
            continue
        try:
            raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        except OSError:
            continue
        cmdline = raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()
        if needle in cmdline:
            rss_kb = 0
            try:
                for line in open(f"/proc/{pid}/status", encoding="utf-8"):
                    if line.startswith("VmRSS:"):
                        rss_kb = int(line.split()[1])
            except OSError:
                pass
            hits.append({"pid": pid, "rss_gb": round(rss_kb / 1048576.0, 2),
                         "cmdline": cmdline[:160]})
    return hits


def check_critical_path():
    print("critical path (must be finished):")
    hits = find_processes(CRITICAL_PATH_NEEDLE)
    if hits:
        for hit in hits:
            fail("critical-path worker still alive",
                 "pid=%d rss=%.2fGB %s" % (hit["pid"], hit["rss_gb"], hit["cmdline"]))
    else:
        ok("no %s process" % CRITICAL_PATH_NEEDLE)
    for needle in ("_b9_calib_driver.py", "_b9_calib_driver_v2.py", "guard_b9"):
        hits = find_processes(needle)
        if hits:
            fail("a previous B9 process is still alive (needle %r)" % needle,
                 ", ".join("pid=%d" % h["pid"] for h in hits))
        else:
            ok("no %s process" % needle)


def check_code():
    print("code under test:")
    if not B9_SRC.is_file():
        fail("b9 port source missing", str(B9_SRC))
        return
    source = B9_SRC.read_text(encoding="utf-8")
    if "QUANTILE_NUMEL_LIMIT = 16_777_216" in source and "_exact_percentiles" in source:
        ok("torch.quantile fix present in", str(B9_SRC))
    else:
        fail("torch.quantile fix NOT present in", str(B9_SRC))
    backup = B9_SRC.with_suffix(".py.bak_quantile_fix")
    if backup.is_file():
        ok("pre-fix backup kept at", backup.name)
    else:
        warn("pre-fix backup missing", backup.name)
    probe = subprocess.run(
        ["/root/miniconda3/bin/python", "-c",
         "import sys; sys.path.insert(0, '/root/mk_v2');"
         "from src.experiments.external_ports import b9_seeded_fuzzing as b;"
         "import torch;"
         "print(b.QUANTILE_NUMEL_LIMIT == 2 ** 24, torch.__version__)"],
        capture_output=True, text=True, cwd=str(MK),
        env={**os.environ, "CUDA_VISIBLE_DEVICES": ""})
    if probe.returncode == 0 and probe.stdout.startswith("True"):
        ok("import + limit check", probe.stdout.strip())
    else:
        fail("import + limit check", (probe.stdout + probe.stderr).strip()[:300])


def check_state():
    print("calibration state:")
    for name in ("task_table.json", "unit_size_table.json"):
        path = OUT_ROOT / name
        if path.is_file():
            ok("present", name)
        else:
            fail("missing (run _b9fix_probe6 / prep first)", name)
    if PAUSE_MARKER.is_file():
        warn("pause marker present; resume_b9.sh will archive it",
             PAUSE_MARKER.name)
    else:
        ok("no pause marker")
    rows = 0
    for path in sorted(OUT_ROOT.glob("calibration_*lane*.jsonl")):
        rows += sum(1 for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip())
    ok("calibration rows on disk", str(rows))


def check_resources(budget_gb):
    print("resources:")
    limit = int(Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")
                .read_text().strip()) / GIB
    usage = int(Path("/sys/fs/cgroup/memory/memory.usage_in_bytes")
                .read_text().strip()) / GIB
    ok("cgroup memory limit", "%.1f GiB" % limit)
    ok("cgroup memory in use", "%.1f GiB" % usage)
    headroom = limit - usage
    if budget_gb > headroom:
        warn("configured budget exceeds current headroom",
             "budget=%.0f GiB headroom=%.1f GiB (page cache is reclaimable)"
             % (budget_gb, headroom))
    else:
        ok("budget fits current headroom", "%.0f <= %.1f GiB" % (budget_gb, headroom))
    smi = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory",
                          "--format=csv,noheader"], capture_output=True, text=True)
    apps = [line for line in smi.stdout.strip().splitlines() if line.strip()]
    if apps:
        fail("GPU is still busy", "; ".join(apps))
    else:
        ok("no GPU compute apps")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget-gb", type=float, default=100.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    print("=== B9 resume precheck ===")
    check_critical_path()
    check_code()
    check_state()
    check_resources(args.budget_gb)
    print()
    if args.json:
        print(json.dumps({"failures": failures, "warnings": warnings}, indent=2))
    if failures:
        print("PRECHECK_FAILED (%d hard failures, %d warnings)"
              % (len(failures), len(warnings)))
        return 1
    print("PRECHECK_OK (%d warnings)" % len(warnings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
