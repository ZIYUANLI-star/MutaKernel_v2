"""OOM-focused watchdog for the E1 equiv heavy-lane split run on the remote A800.

Monitors all equiv lanes (glob lane*), polling every 10 minutes. Alerts on:
- GPU memory above the danger threshold (76 GB of 80 GB)
- any "out of memory" / OOM-killer evidence in lane logs or dmesg
- resource-class INCONCLUSIVE records appearing in lane observations
- lane processes dying without completion markers, or stalled logs
Prints E1_DONE when all active lanes report completion.
"""
import time
from datetime import datetime

import _remote

RUN_DIR = "/root/mk_v2_runs/e1"
LOG_GLOB = "/root/mk_v2_runs/e1_equiv_lane*.log"
INTERVAL_S = 600
STALL_S = 3600  # heavy probes can take 900s each; 1h without log writes is the alarm bar
GPU_DANGER_MIB = 76000
# one known cap-hit record from the old lane0 era (L1_P21__relop_replace__3);
# only alert when NEW resource-flagged records appear beyond this baseline
RESOURCE_BASELINE = 1

consecutive_conn_failures = 0

REMOTE_CMD = (
    # per-lane observation counts
    f"for f in {RUN_DIR}/equiv_observations_lane*.jsonl; do "
    "echo \"$(basename $f) $(wc -l < $f)\"; done; echo __SEP__; "
    # driver process count
    "ps aux | grep 'run_e1_probe_[s]tudy' | grep -v grep | wc -l; echo __SEP__; "
    # freshest log mtime + now
    f"stat -c %Y {LOG_GLOB} 2>/dev/null | sort -n | tail -1; date +%s; echo __SEP__; "
    # OOM evidence in lane logs
    f"grep -ci 'out of memory\\|CUDA error\\|cudaErrorMemoryAllocation' {LOG_GLOB} 2>/dev/null; echo __SEP__; "
    # resource-class inconclusive in observations
    f"grep -c 'resource' {RUN_DIR}/equiv_observations_lane*.jsonl 2>/dev/null; echo __SEP__; "
    # autorestarts + done markers
    f"grep -c AUTORESTART {LOG_GLOB} 2>/dev/null; echo __SEP__; "
    f"grep -l EQUIV_DONE {LOG_GLOB} 2>/dev/null | wc -l; "
    f"ls {LOG_GLOB} 2>/dev/null | wc -l; echo __SEP__; "
    # GPU total + per-process memory
    "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader; "
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>/dev/null; echo __SEP__; "
    # kernel-level OOM killer evidence (last boot)
    "dmesg 2>/dev/null | grep -ci 'out of memory\\|oom-kill'; echo __SEP__; "
    # the requeue lane is the last lane; its EQUIV_DONE marks full completion
    "grep -c EQUIV_DONE /root/mk_v2_runs/e1_equiv_lane4_requeue.log 2>/dev/null"
)


def cycle():
    global consecutive_conn_failures
    try:
        c = _remote.connect()
        _, out, _ = _remote.run(c, REMOTE_CMD, timeout=120, echo=False)
        c.close()
        consecutive_conn_failures = 0
    except Exception as exc:
        consecutive_conn_failures += 1
        print(f"[{datetime.now():%H:%M}] WARN connection failed "
              f"({consecutive_conn_failures}x): {type(exc).__name__}: {str(exc)[:120]}",
              flush=True)
        if consecutive_conn_failures >= 3:
            print("ALERT: three consecutive connection failures", flush=True)
        return

    parts = out.split("__SEP__")
    lane_counts = " ".join(parts[0].split("\n")) if len(parts) > 0 else "?"
    lane_counts = " ".join(lane_counts.split())
    procs = int(parts[1].strip() or 0) if len(parts) > 1 else 0
    times = parts[2].split() if len(parts) > 2 else []
    log_oom_lines = parts[3].strip().replace("\n", " ") if len(parts) > 3 else ""
    obs_resource_lines = parts[4].strip().replace("\n", " ") if len(parts) > 4 else ""
    restarts = parts[5].strip().replace("\n", " ") if len(parts) > 5 else ""
    done_counts = parts[6].split() if len(parts) > 6 else []
    gpu_block = parts[7].strip() if len(parts) > 7 else "?"
    dmesg_oom = (parts[8].strip() or "0") if len(parts) > 8 else "0"
    requeue_done = (parts[9].strip() or "0") if len(parts) > 9 else "0"

    stall_s = None
    if len(times) >= 2:
        try:
            stall_s = int(times[-1]) - int(times[0])
        except ValueError:
            pass

    gpu_lines = gpu_block.split("\n")
    gpu_total = gpu_lines[0] if gpu_lines else "?"
    per_proc = "; ".join(l.strip() for l in gpu_lines[1:] if l.strip())

    gpu_used_mib = None
    try:
        gpu_used_mib = int(gpu_total.split(",")[0].strip().split()[0])
    except (ValueError, IndexError):
        pass

    log_oom_total = sum(int(x.split(":")[-1]) for x in log_oom_lines.split() if ":" in x)
    obs_resource_total = sum(int(x.split(":")[-1]) for x in obs_resource_lines.split() if ":" in x)

    done_lanes = int(done_counts[0]) if len(done_counts) >= 1 and done_counts[0].isdigit() else 0
    total_lanes = int(done_counts[1]) if len(done_counts) >= 2 and done_counts[1].isdigit() else 0

    print(f"[{datetime.now():%H:%M}] obs=[{lane_counts}] procs={procs} log_age_s={stall_s} "
          f"gpu_total=[{gpu_total}] per_proc=[{per_proc}] "
          f"log_oom={log_oom_total} obs_resource={obs_resource_total} "
          f"dmesg_oom={dmesg_oom} restarts=[{restarts}] done={done_lanes}/{total_lanes}",
          flush=True)

    if gpu_used_mib is not None and gpu_used_mib > GPU_DANGER_MIB:
        print(f"ALERT_OOM_RISK: GPU memory {gpu_used_mib} MiB > {GPU_DANGER_MIB} MiB danger bar",
              flush=True)
    if log_oom_total > 0:
        print(f"ALERT_OOM: {log_oom_total} out-of-memory/CUDA-error lines in lane logs",
              flush=True)
    if obs_resource_total > RESOURCE_BASELINE:
        print(f"ALERT_RESOURCE: {obs_resource_total} resource-flagged observation lines "
              f"({obs_resource_total - RESOURCE_BASELINE} new beyond baseline; "
              "will need serial requeue)", flush=True)
    if dmesg_oom != "0":
        print(f"ALERT_OOM: dmesg shows {dmesg_oom} OOM-killer lines", flush=True)

    # lanes 0/2/3 were retired mid-run and never write DONE markers; the
    # requeue lane (lane4) covers all their remaining probes, so its marker
    # plus lane1's historical DONE means the whole equiv phase is complete
    if requeue_done != "0" and procs == 0:
        print("E1_DONE: requeue lane reported completion", flush=True)
        return "done"
    if procs == 0 and requeue_done == "0":
        print("ALERT: no lane process running and requeue lane not done (guard failed?)",
              flush=True)
    if stall_s is not None and stall_s > STALL_S:
        print(f"ALERT: all lane logs stalled for {stall_s}s (> {STALL_S}s)", flush=True)


def main():
    while True:
        try:
            if cycle() == "done":
                break
        except Exception:
            import traceback
            print(f"[{datetime.now():%H:%M}] WATCHDOG_ERROR (loop continues):", flush=True)
            traceback.print_exc()
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    main()
