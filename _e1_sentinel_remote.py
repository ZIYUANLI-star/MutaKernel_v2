"""E1 CSE self-healing sentinel (v1, 2026-07-27).

Deployed to /root/mk_v2/e1_sentinel.py on the A800.  Runs独立于守护 v10.1
(独立 pidfile + flock)，每 10 分钟一轮，自愈优先、停道兜底：

  R1 超时类 INCONCLUSIVE 增长  -> 归档+重排队 + 预算升档重启 (3600->5400)
  R2 资源事件 (mem/oom)        -> 降并发: 停 lane4/5 保 lane3, 恢复后自动重启
  R3 观测停滞 (挂死)           -> 杀挂死驱动让守护重启; 同探针两连挂 -> 移队尾
  R4 FALSIFIED 缺见证字段      -> 隔离该记录 + 探针重排队, 其余照跑, WARN 高亮
  R5 停道兜底                  -> 仅当同一处置连续 2 次失败 / 数据完整性破坏

对活动观测/checkpoint 的写操作仅限 "归档移出 + 重排队" 模式 (先备份)。
不改判级语义, 不改守护脚本。所有杀进程按 PID 树精准操作, 不用 pkill 模式。
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path

# --------------------------------------------------------------------------
# Config (module globals so the drill can re-point them at a sandbox)
# --------------------------------------------------------------------------
RUNS = Path("/root/mk_v2_runs")
E1 = RUNS / "e1"
MK_ROOT = "/root/mk_v2"
PYBIN = "/root/miniconda3/bin/python"
DRY_RUN = False          # drill mode: no real kill/launch, record intent only

INTERVAL_S = 600
LANES = (3, 4, 5)
INC_WINDOW_S = 14400     # rolling window for timeout-INC growth (4 h)
INC_THRESHOLD = 3        # >=3 new timeout-INC inside window => systemic waste
STALL_S = 9000           # 2.5 h without new observation => hung (max probe 5400)
MEM_LIMIT_B = 110 * 1024 ** 3
MEM_RECOVER_B = 90 * 1024 ** 3
RES_INC_PER_CYCLE = 2    # new OOM-void records in one cycle counting as event
DEFAULT_BUDGET = 3600
MAX_BUDGET = 5400        # escalation ladder 3600 -> 5400 (env config, not语义)
ACTION_COOLDOWN_S = 1800
MAX_ATTEMPTS = 2         # same remediation failing twice consecutively => halt

_LOCK_FD = None          # kept open for the process lifetime (flock)


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def log(msg):
    print(f"[sentinel {now_iso()}] {msg}", flush=True)


# --------------------------------------------------------------------------
# Paths (functions so RUNS/E1 overrides take effect at call time)
# --------------------------------------------------------------------------
def obs_path(lane):
    return E1 / f"cse_observations_lane{lane}.jsonl"


def done_path(lane):
    return E1 / f"cse_completed_lane{lane}.json"


def lane_log_path(lane):
    return RUNS / f"e1_cse_lane{lane}.log"


def plan_path():
    return E1 / "cse_lane_plan.json"


def halt_path():
    return RUNS / "ANOMALY_HALT.json"


def warn_path():
    return RUNS / "ANOMALY_WARN.json"


def heartbeat_path():
    return RUNS / "sentinel_heartbeat.jsonl"


def actions_log_path():
    return RUNS / "sentinel_actions.jsonl"


def state_path():
    return RUNS / "e1_sentinel_state.json"


def done_marker(lane):
    return E1 / f"CSE_DONE_LANE{lane}"


# --------------------------------------------------------------------------
# Observation parsing / record classification (pure, drill-tested)
# --------------------------------------------------------------------------
def parse_obs(lane):
    """Read one lane's observations; tolerate an in-flight (torn) tail line.

    Returns (records, bad_mid_lines): mid-file unparseable lines are an
    integrity signal, an unparseable *last* line is a legal in-flight append.
    """
    path = obs_path(lane)
    recs, bad_mid = [], 0
    if not path.exists():
        return recs, bad_mid
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, ln in enumerate(lines):
        if not ln.strip():
            continue
        try:
            recs.append(json.loads(ln))
        except ValueError:
            if i != len(lines) - 1:
                bad_mid += 1
    return recs, bad_mid


def is_timeout_inc(r):
    return (r.get("outcome") == "INCONCLUSIVE"
            and (r.get("timed_out") is True
                 or r.get("inconclusive_class") == "timeout"))


def is_resource_inc(r):
    return (r.get("outcome") == "INCONCLUSIVE"
            and r.get("inconclusive_class") == "out_of_memory")


def bad_witness(r):
    """FALSIFIED record missing any of the witness triple => quality anomaly."""
    if r.get("outcome") != "FALSIFIED":
        return False
    return any(r.get(k) in (None, "")
               for k in ("witness_policy", "witness_round", "witness_seed"))


def inc_growth(history, now):
    """Growth of the timeout-INC counter inside the rolling window."""
    hist = [h for h in history if now - h[0] <= INC_WINDOW_S]
    if len(hist) >= 2:
        return hist[-1][1] - hist[0][1]
    return 0


def decide_resource(mem_used, new_oom, new_res_inc, prev_streak):
    """Resource state machine: returns (new_streak, action).

    action: None | 'warn' (first strike) | 'pause' (second consecutive strike).
    """
    event = ((mem_used is not None and mem_used > MEM_LIMIT_B)
             or new_oom > 0 or new_res_inc >= RES_INC_PER_CYCLE)
    if not event:
        return 0, None
    streak = prev_streak + 1
    return streak, ("pause" if streak >= 2 else "warn")


def is_stalled(obs_age, driver_age, driver_alive):
    """Hung: driver alive but no new observation for STALL_S (both clocks)."""
    if not driver_alive or obs_age is None:
        return False
    ref = obs_age if driver_age is None else min(obs_age, driver_age)
    return ref > STALL_S


# --------------------------------------------------------------------------
# Process handling (PID-precise, never pattern-kill)
# --------------------------------------------------------------------------
def list_procs():
    procs = []
    for pd in Path("/proc").iterdir():
        if not pd.name.isdigit():
            continue
        try:
            cmd = (pd / "cmdline").read_bytes().decode(
                errors="replace").replace("\x00", " ").strip()
            stat = (pd / "stat").read_text()
        except OSError:
            continue
        if not cmd:
            continue
        try:
            ppid = int(stat.rsplit(")", 1)[1].split()[1])
        except (IndexError, ValueError):
            continue
        procs.append({"pid": int(pd.name), "ppid": ppid, "cmd": cmd})
    return procs


def driver_of(procs, lane):
    for p in procs:
        c = p["cmd"]
        if ("run_e1_cse_falsify.py" in c and "python" in c
                and c.rstrip().endswith(f"--lane {lane}")):
            return p
    return None


def proc_age_s(pid):
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        start_jiffies = int(stat.rsplit(")", 1)[1].split()[19])
        uptime = float(Path("/proc/uptime").read_text().split()[0])
        clk = os.sysconf("SC_CLK_TCK")
        return uptime - start_jiffies / clk
    except (OSError, IndexError, ValueError):
        return None


def tree_pids(procs, root_pid):
    kids = {}
    for p in procs:
        kids.setdefault(p["ppid"], []).append(p["pid"])
    out, i = [root_pid], 0
    while i < len(out):
        out.extend(kids.get(out[i], []))
        i += 1
    return out


def kill_pids(pids, ev, note):
    ev["actions"].append({"op": "kill", "pids": pids, "note": note,
                          "dry_run": DRY_RUN})
    if DRY_RUN:
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in pids:
            try:
                os.kill(pid, sig)
            except OSError:
                pass
        if sig == signal.SIGTERM:
            time.sleep(3)


def kill_lane_tree(procs, lane, ev, note):
    drv = driver_of(procs, lane)
    if drv is None:
        return False
    kill_pids(tree_pids(procs, drv["pid"]), ev, f"lane{lane}: {note}")
    return True


def current_probe(procs, driver_pid):
    """Identify the probe currently executing under a driver.

    The worker cmdline carries the config path cfg_<probe_id>.json (E0
    pattern), so the hung probe is readable straight off the process table.
    """
    for pid in tree_pids(procs, driver_pid)[1:]:
        for p in procs:
            if p["pid"] != pid:
                continue
            for tok in p["cmd"].split():
                base = tok.rsplit("/", 1)[-1]
                if base.startswith("cfg_") and base.endswith(".json"):
                    return base[4:-5]
    return None


def guard_pid_alive():
    pidfile = RUNS / "e1_guard.pid"
    try:
        pid = int(pidfile.read_text().strip())
    except (OSError, ValueError):
        return None, False
    try:
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes().decode(
            errors="replace")
    except OSError:
        return pid, False
    return pid, ("e1_guard" in cmd)


def stop_guard(ev):
    pid, alive = guard_pid_alive()
    ev["actions"].append({"op": "stop_guard", "pid": pid, "alive": alive,
                          "dry_run": DRY_RUN})
    if DRY_RUN or not alive:
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    try:
        (RUNS / "e1_guard.pid").unlink()
    except OSError:
        pass


def start_guard(ev):
    ev["actions"].append({"op": "start_guard", "dry_run": DRY_RUN})
    if DRY_RUN:
        return
    with open(os.devnull, "wb") as devnull:
        subprocess.Popen(["bash", str(RUNS / "e1_guard.sh")],
                         stdout=devnull, stderr=devnull,
                         start_new_session=True)


def launch_lane(lane, budget, ev):
    frac = "0.92" if lane == 3 else "0.45"
    ev["actions"].append({"op": "launch_lane", "lane": lane,
                          "budget": budget, "frac": frac, "dry_run": DRY_RUN})
    if DRY_RUN:
        return
    env = {
        "PATH": "/usr/local/cuda/bin:/root/miniconda3/bin:"
                "/usr/local/bin:/usr/bin:/bin",
        "TORCH_EXTENSIONS_DIR": str(RUNS / "torch_ext"),
        "MK_GPU_MEMORY_FRACTION": frac,
        "HOME": "/root",
    }
    lane_log = open(lane_log_path(lane), "ab")
    subprocess.Popen(
        [PYBIN, "-u", "scripts/run_e1_cse_falsify.py",
         "--out-dir", str(E1), "--kernelbench-root", "KernelBench",
         "--timeout", str(budget),
         "--lane-plan", str(plan_path()), "--lane", str(lane)],
        cwd=MK_ROOT, env=env, stdout=lane_log, stderr=lane_log,
        start_new_session=True)


def driver_up(lane, wait_s=10):
    if DRY_RUN:
        return True
    time.sleep(wait_s)
    return driver_of(list_procs(), lane) is not None


# --------------------------------------------------------------------------
# File surgery: the only writes ever made to obs/checkpoint files.
# Pattern (人工验证过的既有模式): backup -> move matching lines to an archive
# -> rewrite obs -> drop the same ids from the lane's completed checkpoint.
# Caller must have stopped the lane driver first.
# --------------------------------------------------------------------------
def requeue(lane, predicate, archive_name, reason, ev):
    obs, done = obs_path(lane), done_path(lane)
    ts = time.strftime("%Y%m%d-%H%M%S")
    kept_raw, moved_raw, moved_ids = [], [], []
    for ln in obs.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            rec = json.loads(ln)
        except ValueError:
            kept_raw.append(ln)
            continue
        if predicate(rec):
            moved_raw.append(ln)
            moved_ids.append(rec.get("probe_id"))
        else:
            kept_raw.append(ln)
    if not moved_ids:
        ev["actions"].append({"op": "requeue", "lane": lane, "moved": 0,
                              "reason": reason})
        return []
    shutil.copy2(obs, str(obs) + f".bak_sentinel_{ts}")
    if done.exists():
        shutil.copy2(done, str(done) + f".bak_sentinel_{ts}")
    archive = E1 / archive_name
    with open(archive, "a", encoding="utf-8") as fh:
        for ln in moved_raw:
            fh.write(ln + "\n")
    obs.write_text("".join(l + "\n" for l in kept_raw), encoding="utf-8")
    completed = json.loads(done.read_text()) if done.exists() else []
    done.write_text(json.dumps(sorted(set(completed) - set(moved_ids))),
                    encoding="utf-8")
    ev["actions"].append({"op": "requeue", "lane": lane, "reason": reason,
                          "moved": len(moved_ids), "ids": moved_ids,
                          "archive": str(archive), "backup_ts": ts})
    return moved_ids


def plan_move_kernel_to_tail(lane, kernel, ev):
    path = plan_path()
    ts = time.strftime("%Y%m%d-%H%M%S")
    plan = json.loads(path.read_text(encoding="utf-8"))
    kernels = plan["lanes"][lane]["kernels"]
    if kernel not in kernels:
        ev["actions"].append({"op": "plan_tail", "lane": lane,
                              "kernel": kernel, "result": "not_in_lane"})
        return False
    shutil.copy2(path, str(path) + f".bak_sentinel_{ts}")
    kernels.remove(kernel)
    kernels.append(kernel)
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    ev["actions"].append({"op": "plan_tail", "lane": lane, "kernel": kernel,
                          "result": "moved", "backup_ts": ts})
    return True


def write_budget_note(lane, budget, reason):
    """Manifest side-note: budget is environment config, recorded for audit.

    The driver's own run manifest will also carry timeout_s on restart; this
    file preserves the sentinel's escalations across manifest rewrites.
    """
    path = E1 / "sentinel_budget_overrides.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {"note": "probe budget escalations by sentinel (env config, "
                        "not grading semantics)", "overrides": []}
    data["overrides"].append({"at": now_iso(), "lane": lane,
                              "timeout_s": budget, "reason": reason})
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------
# WARN / HALT / action bookkeeping
# --------------------------------------------------------------------------
def add_warn(kind, detail):
    try:
        data = json.loads(warn_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {"warnings": []}
    data["warnings"].append({"at": now_iso(), "kind": kind, "detail": detail})
    data["warnings"] = data["warnings"][-200:]
    warn_path().write_text(json.dumps(data, indent=2, ensure_ascii=False),
                           encoding="utf-8")


def do_halt(state, reason, evidence, ev):
    """Fallback halt: idempotent (no-op when ANOMALY_HALT.json exists)."""
    if halt_path().exists():
        return
    halt_path().write_text(json.dumps({
        "at": now_iso(), "reason": reason, "evidence": evidence,
        "recovery": "人工检查证据 -> 修复根因 -> 删除 ANOMALY_HALT.json -> "
                    "bash /root/mk_v2_runs/e1_guard.sh (守护会从 checkpoint 续跑)",
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    ev["actions"].append({"op": "HALT", "reason": reason})
    stop_guard(ev)
    procs = list_procs()
    for lane in LANES:
        kill_lane_tree(procs, lane, ev, f"halt: {reason}")
    log(f"HALT: {reason}")


def record_action(state, key, ok, info, ev):
    entry = state["actions"].setdefault(
        key, {"count": 0, "fails": 0, "last_ts": 0})
    entry["count"] += 1
    entry["last_ts"] = time.time()
    entry["fails"] = 0 if ok else entry["fails"] + 1
    row = {"at": now_iso(), "key": key, "ok": ok, "info": info,
           "consecutive_fails": entry["fails"]}
    ev["actions"].append({"op": "action_result", **row})
    try:
        with open(actions_log_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return entry


def cooled_down(state, key):
    last = state["actions"].get(key, {}).get("last_ts", 0)
    return time.time() - last >= ACTION_COOLDOWN_S


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------
def default_state():
    return {
        "started_at": now_iso(),
        "lanes": {str(l): {"inc_hist": [], "res_inc_n": 0, "budget":
                           DEFAULT_BUDGET, "last_stall_probe": None}
                  for l in LANES},
        "actions": {},
        "oom_count": None,
        "res_streak": 0,
        "paused_parallel": None,
        "quarantine_counts": {},
        "integrity_baseline": None,
        "integrity_pending": {},
    }


def load_state():
    try:
        st = json.loads(state_path().read_text(encoding="utf-8"))
        base = default_state()
        base.update(st)
        for l in LANES:
            base["lanes"].setdefault(str(l), default_state()["lanes"][str(l)])
        return base
    except (OSError, ValueError):
        return default_state()


def save_state(state):
    tmp = state_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
    tmp.replace(state_path())


# --------------------------------------------------------------------------
# Environment probes
# --------------------------------------------------------------------------
def mem_used_bytes():
    for p in ("/sys/fs/cgroup/memory.current",
              "/sys/fs/cgroup/memory/memory.usage_in_bytes"):
        try:
            v = int(Path(p).read_text().strip())
            if v < (1 << 62):        # ignore "unlimited" style sentinels
                return v
        except (OSError, ValueError):
            pass
    try:
        info = {}
        for ln in Path("/proc/meminfo").read_text().splitlines():
            k, v = ln.split(":", 1)
            info[k] = int(v.split()[0]) * 1024
        return info["MemTotal"] - info["MemAvailable"]
    except (OSError, KeyError, ValueError):
        return None


def oom_kill_count():
    try:
        r = subprocess.run(
            "dmesg 2>/dev/null | grep -ciE 'oom-kill|killed process' || true",
            shell=True, capture_output=True, text=True, timeout=30)
        return int((r.stdout or "0").strip() or 0)
    except (subprocess.SubprocessError, ValueError):
        return None


def gpu_mem_used_mib():
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=30)
        return [int(x) for x in r.stdout.split() if x.strip().isdigit()]
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


# --------------------------------------------------------------------------
# Lane snapshot
# --------------------------------------------------------------------------
def snapshot_lane(lane, procs, now):
    recs, bad_mid = parse_obs(lane)
    drv = driver_of(procs, lane)
    op = obs_path(lane)
    obs_age = (now - op.stat().st_mtime) if op.exists() else None
    return {
        "records": recs,
        "bad_mid_lines": bad_mid,
        "obs": len(recs),
        "inc": sum(1 for r in recs if r.get("outcome") == "INCONCLUSIVE"),
        "inc_timeout": sum(1 for r in recs if is_timeout_inc(r)),
        "inc_resource": sum(1 for r in recs if is_resource_inc(r)),
        "falsified": sum(1 for r in recs if r.get("outcome") == "FALSIFIED"),
        "bad_witness": [r for r in recs if bad_witness(r)],
        "last_outcome": (recs[-1].get("outcome") if recs else None),
        "driver_pid": (drv["pid"] if drv else None),
        "driver_age_s": (proc_age_s(drv["pid"]) if drv else None),
        "obs_age_s": obs_age,
        "done": done_marker(lane).exists(),
    }


def active_lanes(snaps):
    """Lanes expected to be producing right now (lane5 chained after lane4)."""
    out = []
    for lane in LANES:
        if snaps[lane]["done"]:
            continue
        if lane == 5 and not done_marker(4).exists():
            continue
        out.append(lane)
    return out


# --------------------------------------------------------------------------
# Handbook rules (each returns True when it performed the cycle's action)
# --------------------------------------------------------------------------
def integrity_check(state, snaps, ev):
    """R5b: checkpoint accounting breakage that requeue cannot isolate.

    Baselined on first sight (lane reorganisations legally leave completed
    ids whose obs lines live in other lanes' files); only *new* divergence
    counts, and it must persist two consecutive cycles before the halt.
    """
    current = {}
    for lane in LANES:
        ids = [r.get("probe_id") for r in snaps[lane]["records"]
               if r.get("probe_id")]
        dups = sorted({i for i in ids if ids.count(i) > 1})
        try:
            completed = set(json.loads(done_path(lane).read_text()))
        except (OSError, ValueError):
            completed = set()
        missing = sorted(completed - set(ids))
        current[str(lane)] = {"dups": dups, "missing": missing,
                              "bad_mid_lines": snaps[lane]["bad_mid_lines"]}
    if state["integrity_baseline"] is None:
        state["integrity_baseline"] = current
        return False
    problems = {}
    for lane_s, cur in current.items():
        base = state["integrity_baseline"].get(lane_s, {})
        new_dups = sorted(set(cur["dups"]) - set(base.get("dups", [])))
        new_missing = sorted(set(cur["missing"])
                             - set(base.get("missing", [])))
        new_bad = cur["bad_mid_lines"] - base.get("bad_mid_lines", 0)
        if new_dups or new_bad > 0:
            problems[lane_s] = {"new_dups": new_dups, "new_bad_mid": new_bad}
        elif new_missing:
            # completed id without an obs line: tolerate one in-flight cycle
            problems[lane_s] = {"new_missing": new_missing}
    persistent = {k: v for k, v in problems.items()
                  if state["integrity_pending"].get(k) == v}
    state["integrity_pending"] = problems
    if persistent:
        do_halt(state, "integrity_breakage_unrecoverable_by_requeue",
                persistent, ev)
        return True
    if problems:
        add_warn("integrity_pending", problems)
    return False


def rule4_quality(state, snaps, ev):
    """R4: quarantine FALSIFIED records missing the witness triple; requeue
    the probe; everything else keeps running; WARN highlights the likely
    code bug for human patching."""
    for lane in LANES:
        bad = snaps[lane]["bad_witness"]
        if not bad:
            continue
        ids = [r.get("probe_id") for r in bad]
        repeat = [i for i in ids
                  if state["quarantine_counts"].get(i, 0) >= MAX_ATTEMPTS]
        if repeat:
            do_halt(state, "rule4_quarantine_ineffective_twice",
                    {"lane": lane, "probe_ids": repeat}, ev)
            return True
        key = f"rule4_lane{lane}"
        if not cooled_down(state, key):
            continue
        log(f"R4 trigger lane{lane}: FALSIFIED missing witness {ids}")
        stop_guard(ev)
        procs = list_procs()
        kill_lane_tree(procs, lane, ev, "rule4 quarantine surgery")
        moved = requeue(
            lane, lambda r: bad_witness(r) and r.get("probe_id") in ids,
            f"cse_observations_lane{lane}_quarantine.jsonl",
            "FALSIFIED missing witness fields", ev)
        for i in moved:
            state["quarantine_counts"][i] = (
                state["quarantine_counts"].get(i, 0) + 1)
        launch_lane(lane, state["lanes"][str(lane)]["budget"], ev)
        start_guard(ev)
        ok = driver_up(lane) and bool(moved)
        add_warn("rule4_quality_quarantine", {
            "lane": lane, "probe_ids": moved,
            "note": "疑似判级代码 bug: FALSIFIED 缺 witness 三元组, 已隔离归档"
                    "+重排队, 实验继续; 请人工修码后关注该探针复跑结果"})
        entry = record_action(state, key, ok,
                              {"lane": lane, "quarantined": moved}, ev)
        if entry["fails"] >= MAX_ATTEMPTS:
            do_halt(state, "rule4_action_failed_twice", {"lane": lane}, ev)
        return True
    return False


def rule2_resource(state, snaps, ev, mem_used, new_oom, new_res_inc):
    """R2: degrade concurrency instead of halting.  Two consecutive strikes
    pause lanes 4/5 (queues stay intact -> auto-requeued by checkpoint);
    lane3 keeps the GPU busy; parallel lanes auto-resume on recovery."""
    paused = state["paused_parallel"]
    if paused:
        # Babysit lane3 while the guard is intentionally down.
        if (not snaps[3]["done"] and snaps[3]["driver_pid"] is None
                and not DRY_RUN):
            launch_lane(3, state["lanes"]["3"]["budget"], ev)
        recovered = ((mem_used is None or mem_used < MEM_RECOVER_B)
                     and new_oom == 0 and new_res_inc == 0)
        if recovered:
            log("R2 resume: resources recovered, restarting parallel lanes")
            start_guard(ev)   # guard v10.1 relaunches lane4 (lane5 chained)
            state["paused_parallel"] = None
            state["res_streak"] = 0
            if DRY_RUN:
                ok = True
            else:
                time.sleep(5)
                _, ok = guard_pid_alive()   # lane4 launch follows within 120s
            entry = record_action(state, "rule2_resume", ok,
                                  {"paused_since": paused.get("at")}, ev)
            if entry["fails"] >= MAX_ATTEMPTS:
                do_halt(state, "rule2_resume_failed_twice", paused, ev)
            return True
        ev["actions"].append({"op": "rule2_hold_pause",
                              "mem_used": mem_used, "new_oom": new_oom})
        return False
    streak, action = decide_resource(mem_used, new_oom, new_res_inc,
                                     state["res_streak"])
    state["res_streak"] = streak
    if action is None:
        return False
    evidence = {"mem_used_gb": (round(mem_used / 2**30, 1)
                                if mem_used is not None else None),
                "new_oom_kills": new_oom, "new_oom_void_records": new_res_inc}
    if action == "warn":
        add_warn("rule2_resource_first_strike", evidence)
        log(f"R2 first strike: {evidence}")
        return False
    log(f"R2 pause parallel lanes: {evidence}")
    stop_guard(ev)                      # must die first or it resurrects lane4
    procs = list_procs()
    for lane in (4, 5):
        kill_lane_tree(procs, lane, ev, "rule2 degrade concurrency")
    state["paused_parallel"] = {"at": now_iso(), "evidence": evidence}
    add_warn("rule2_parallel_paused", {
        **evidence, "note": "已降并发: lane4/5 暂停(探针原地保留在队列), "
        "lane3 继续; 资源恢复后哨兵自动重启并行道"})
    ok = True if DRY_RUN else (driver_of(list_procs(), 4) is None)
    entry = record_action(state, "rule2_pause", ok, evidence, ev)
    if entry["fails"] >= MAX_ATTEMPTS:
        do_halt(state, "rule2_pause_failed_twice", evidence, ev)
    return True


def rule1_timeout_inc(state, snaps, ev, now):
    """R1: timeout-INC growth => archive + requeue + budget escalation."""
    for lane in active_lanes(snaps):
        ls = state["lanes"][str(lane)]
        growth = inc_growth(ls["inc_hist"], now)
        if growth < INC_THRESHOLD:
            continue
        new_recs = [r for r in snaps[lane]["records"] if is_timeout_inc(r)]
        if not new_recs:
            ls["inc_hist"] = []
            continue
        key = f"rule1_lane{lane}"
        entry = state["actions"].get(key, {"count": 0, "fails": 0})
        if entry["count"] >= MAX_ATTEMPTS:
            do_halt(state, "rule1_escalation_ineffective_twice",
                    {"lane": lane, "growth": growth,
                     "budget": ls["budget"]}, ev)
            return True
        if not cooled_down(state, key):
            continue
        budget = MAX_BUDGET
        log(f"R1 trigger lane{lane}: +{growth} timeout-INC in window; "
            f"requeue + escalate budget {ls['budget']} -> {budget}")
        stop_guard(ev)
        procs = list_procs()
        kill_lane_tree(procs, lane, ev, "rule1 budget escalation surgery")
        moved = requeue(lane, is_timeout_inc,
                        f"cse_observations_lane{lane}_sentinel_requeue.jsonl",
                        f"timeout-INC growth +{growth} in "
                        f"{INC_WINDOW_S}s window", ev)
        ls["budget"] = budget
        write_budget_note(lane, budget,
                          f"rule1 timeout-INC growth +{growth}")
        launch_lane(lane, budget, ev)
        start_guard(ev)
        ls["inc_hist"] = []
        ok = driver_up(lane) and bool(moved)
        entry = record_action(state, key, ok,
                              {"lane": lane, "requeued": moved,
                               "budget": budget}, ev)
        if entry["fails"] >= MAX_ATTEMPTS:
            do_halt(state, "rule1_action_failed_twice", {"lane": lane}, ev)
        return True
    return False


def rule3_stall(state, snaps, ev):
    """R3: kill a hung driver (guard restarts it from checkpoint); two
    consecutive hangs on the same probe move its kernel to the queue tail."""
    procs = list_procs()
    for lane in active_lanes(snaps):
        s = snaps[lane]
        if state["paused_parallel"] and lane in (4, 5):
            continue
        if not is_stalled(s["obs_age_s"], s["driver_age_s"],
                          s["driver_pid"] is not None):
            continue
        key = f"rule3_lane{lane}"
        if not cooled_down(state, key):
            continue
        ls = state["lanes"][str(lane)]
        probe = current_probe(procs, s["driver_pid"]) if s["driver_pid"] \
            else None
        same_probe = probe is not None and probe == ls["last_stall_probe"]
        log(f"R3 trigger lane{lane}: stalled "
            f"(obs_age={s['obs_age_s']:.0f}s) probe={probe} "
            f"same_as_last={same_probe}")
        if same_probe:
            kernel = probe.split("__", 1)[0]
            stop_guard(ev)
            kill_lane_tree(procs, lane, ev,
                           "rule3 second hang on same probe")
            moved = plan_move_kernel_to_tail(lane, kernel, ev)
            launch_lane(lane, ls["budget"], ev)
            start_guard(ev)
            ls["last_stall_probe"] = None
            ok = driver_up(lane)
            add_warn("rule3_probe_moved_to_tail",
                     {"lane": lane, "probe": probe, "kernel": kernel,
                      "plan_updated": moved})
            entry = record_action(state, key + "_tail", ok,
                                  {"lane": lane, "probe": probe}, ev)
            if entry["fails"] >= MAX_ATTEMPTS:
                do_halt(state, "rule3_tail_move_failed_twice",
                        {"lane": lane, "probe": probe}, ev)
        else:
            kill_lane_tree(procs, lane, ev, "rule3 hung driver kill")
            ls["last_stall_probe"] = probe
            _, guard_alive = guard_pid_alive()
            if not guard_alive and not DRY_RUN:
                start_guard(ev)
            ok = True if DRY_RUN else (
                driver_of(list_procs(), lane) is None)
            entry = record_action(state, key, ok,
                                  {"lane": lane, "probe": probe,
                                   "obs_age_s": s["obs_age_s"]}, ev)
            if entry["fails"] >= MAX_ATTEMPTS:
                do_halt(state, "rule3_kill_failed_twice",
                        {"lane": lane}, ev)
        return True
    return False


def babysit_guard(state, snaps, ev):
    """Liveness: guard died and lanes still pending => restart it (unless we
    paused the parallel lanes on purpose)."""
    if state["paused_parallel"] or halt_path().exists():
        return
    _, alive = guard_pid_alive()
    if not alive and active_lanes(snaps) and not (E1 / "CSE_DONE").exists():
        log("guard missing while lanes pending -> restarting guard")
        start_guard(ev)


# --------------------------------------------------------------------------
# Cycle
# --------------------------------------------------------------------------
def cycle(state):
    now = time.time()
    ev = {"actions": []}
    procs = list_procs()
    snaps = {lane: snapshot_lane(lane, procs, now) for lane in LANES}

    # environment probes + deltas
    mem_used = mem_used_bytes()
    oom = oom_kill_count()
    prev_oom = state.get("oom_count")
    new_oom = max(0, (oom or 0) - (prev_oom or 0)) \
        if (oom is not None and prev_oom is not None) else 0
    state["oom_count"] = oom if oom is not None else prev_oom
    new_res_inc = 0
    for lane in LANES:
        ls = state["lanes"][str(lane)]
        new_res_inc += max(0, snaps[lane]["inc_resource"] - ls["res_inc_n"])
        ls["res_inc_n"] = snaps[lane]["inc_resource"]
        ls["inc_hist"].append([now, snaps[lane]["inc_timeout"]])
        ls["inc_hist"] = [h for h in ls["inc_hist"]
                          if now - h[0] <= INC_WINDOW_S]

    halted = halt_path().exists()
    if not halted:
        acted = integrity_check(state, snaps, ev)
        acted = acted or rule4_quality(state, snaps, ev)
        acted = acted or rule2_resource(state, snaps, ev,
                                        mem_used, new_oom, new_res_inc)
        acted = acted or rule1_timeout_inc(state, snaps, ev, now)
        acted = acted or rule3_stall(state, snaps, ev)
        if not acted:
            babysit_guard(state, snaps, ev)

    guard_pid, guard_alive = guard_pid_alive()
    hb = {
        "ts": round(now, 1), "at": now_iso(),
        "mode": ("halted" if halt_path().exists()
                 else "degraded" if state["paused_parallel"] else "normal"),
        "lanes": {str(l): dict(
                      {k: snaps[l][k] for k in
                       ("obs", "inc", "inc_timeout", "inc_resource",
                        "falsified", "last_outcome", "driver_pid", "done")},
                      obs_age_s=(round(snaps[l]["obs_age_s"])
                                 if snaps[l]["obs_age_s"] is not None
                                 else None),
                      budget=state["lanes"][str(l)]["budget"])
                  for l in LANES},
        "mem_used_gb": (round(mem_used / 2**30, 1)
                        if mem_used is not None else None),
        "gpu_mem_used_mib": gpu_mem_used_mib(),
        "oom_kill_lines": oom,
        "guard": {"pid": guard_pid, "alive": guard_alive},
        "n_drivers": sum(1 for l in LANES
                         if snaps[l]["driver_pid"] is not None),
        "res_streak": state["res_streak"],
        "paused_parallel": bool(state["paused_parallel"]),
        "actions": ev["actions"],
    }
    with open(heartbeat_path(), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(hb, ensure_ascii=False) + "\n")
    save_state(state)
    return hb


# --------------------------------------------------------------------------
# Main (anti-suicide: flock single instance, try/except loop, never exits)
# --------------------------------------------------------------------------
def acquire_lock():
    global _LOCK_FD
    import fcntl
    _LOCK_FD = open(RUNS / "e1_sentinel.lock", "w")
    try:
        fcntl.flock(_LOCK_FD, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("sentinel already running (flock busy); exiting", flush=True)
        raise SystemExit(0)
    _LOCK_FD.write(str(os.getpid()))
    _LOCK_FD.flush()
    (RUNS / "e1_sentinel.pid").write_text(str(os.getpid()))


def main():
    once = "--once" in sys.argv
    acquire_lock()
    log(f"sentinel started pid={os.getpid()} interval={INTERVAL_S}s "
        f"(self-heal first, halt as last resort)")
    state = load_state()
    while True:
        try:
            hb = cycle(state)
            log(f"cycle ok mode={hb['mode']} "
                f"obs={[hb['lanes'][str(l)]['obs'] for l in LANES]} "
                f"actions={len(hb['actions'])}")
        except Exception:
            log("cycle FAILED (sentinel stays up):\n" + traceback.format_exc())
            try:
                save_state(state)
            except Exception:
                pass
        if once:
            break
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    main()
