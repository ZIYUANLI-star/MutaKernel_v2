"""One monitoring cycle for the CSE run; invoked as a subprocess by _watch_cse.py.

Prints a status line, any ALERT_* lines, and a machine-readable INCCOUNTS line
that the parent uses to detect INCONCLUSIVE growth. Exits after one cycle so a
paramiko hang can be killed by the parent instead of freezing the watchdog.
"""
import sys

import _remote

RUN_DIR = "/root/mk_v2_runs/e1"
LOG_GLOB = "/root/mk_v2_runs/e1_cse_lane*.log"
# three capped workers plateau at ~79.9GB by design; alert only near the
# physical 81.9GB ceiling (process-level errors are caught via log_err anyway)
GPU_DANGER_MIB = 81000

# lane?.jsonl only: excludes archived *_timeout_v1 etc.
ACTIVE_GLOB = f"{RUN_DIR}/cse_observations_lane?.jsonl"

REMOTE_CMD = (
    f"for f in {ACTIVE_GLOB}; do echo \"$(basename $f) $(wc -l < $f)\"; done; echo __SEP__; "
    f"for f in {ACTIVE_GLOB}; do "
    "echo \"$(basename $f) $(grep -c '\\\"outcome\\\": \\\"INCONCLUSIVE\\\"' $f)\"; done; echo __SEP__; "
    "ps aux | grep 'run_e1_cse_[f]alsify' | grep -v grep | wc -l; echo __SEP__; "
    f"stat -c %Y {LOG_GLOB} 2>/dev/null | sort -n | tail -1; date +%s; echo __SEP__; "
    f"grep -ci 'out of memory\\|CUDA error\\|Traceback' {LOG_GLOB} 2>/dev/null; echo __SEP__; "
    "ls /root/mk_v2_runs/e1/CSE_DONE_LANE* 2>/dev/null | wc -l; echo __SEP__; "
    "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader; "
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>/dev/null"
)


def main():
    try:
        c = _remote.connect()
        _, out, _ = _remote.run(c, REMOTE_CMD, timeout=120, echo=False)
        c.close()
    except Exception as exc:
        print(f"WARN connection failed: {type(exc).__name__}: {str(exc)[:120]}")
        sys.exit(2)

    parts = out.split("__SEP__")
    obs = " ".join((parts[0] if parts else "?").split())
    inc_raw = parts[1].split("\n") if len(parts) > 1 else []
    procs = int(parts[2].strip() or 0) if len(parts) > 2 else 0
    times = parts[3].split() if len(parts) > 3 else []
    err_raw = parts[4].strip().replace("\n", " ") if len(parts) > 4 else ""
    done_markers = int(parts[5].strip() or 0) if len(parts) > 5 else 0
    gpu_block = parts[6].strip() if len(parts) > 6 else "?"

    inc_pairs = []
    for line in inc_raw:
        toks = line.split()
        if len(toks) == 2 and toks[1].isdigit():
            lane = toks[0].replace("cse_observations_", "").replace(".jsonl", "")
            inc_pairs.append(f"{lane}={toks[1]}")

    stall_s = None
    if len(times) >= 2:
        try:
            stall_s = int(times[-1]) - int(times[0])
        except ValueError:
            pass

    gpu_lines = gpu_block.split("\n")
    gpu_total = gpu_lines[0] if gpu_lines else "?"
    per_proc = "; ".join(l.strip() for l in gpu_lines[1:] if l.strip())
    err_total = sum(int(x.split(":")[-1]) for x in err_raw.split() if ":" in x)

    print(f"obs=[{obs}] procs={procs} log_age_s={stall_s} gpu_total=[{gpu_total}] "
          f"per_proc=[{per_proc}] log_err={err_total} done_markers={done_markers}")
    print("INCCOUNTS " + " ".join(inc_pairs))

    try:
        gpu_used = int(gpu_total.split(",")[0].strip().split()[0])
        if gpu_used > GPU_DANGER_MIB:
            print(f"ALERT_OOM_RISK: GPU memory {gpu_used} MiB > {GPU_DANGER_MIB} MiB")
    except (ValueError, IndexError):
        pass
    if err_total > 0:
        print(f"ALERT_ERR: {err_total} OOM/CUDA-error/Traceback lines in CSE logs")
    if procs == 0 and done_markers < 5:
        print("ALERT: no CSE process running and lanes incomplete (guard failed?)")
    if stall_s is not None and stall_s > 4200:
        print(f"ALERT: CSE logs stalled for {stall_s}s")
    if done_markers >= 5 and procs == 0:
        print("CSE_ALL_DONE")


if __name__ == "__main__":
    main()
