#!/usr/bin/env python3
"""WC-1 followup audit + B9 fp16 fix wave, chained after stage-1 drains.

Advisor-signed plan 2026-07-31 (WC1_daoshi_juece_20260731):
  step 1  wait for STAGE1_DONE + no lane drivers + idle GPU
  step 2  hold the signed brake as owner "wc_followup"
  step 3  back up audit cells + wc1_report for the 8 followup kernels
  step 4  _wc_audit.py run --stage all --only <8 kernels> --force --n-a 15
  step 5  regenerate wc1_report.json via _wc_analyze.py
  step 6  patch scripts/run_e3_external.py (FP16FIX: candidate.to(dtype))
  step 7  canary: run one dtype-bug unit into scratch, expect no dtype error
  step 8  requeue every dtype-bug fp16 unit as wave v2_stage1_fp16_fix
  step 9  release the brake, ensure the guard runs
  step 10 wait for the fix wave to drain, write WCFU_DONE with a summary

Failure mode: any abort leaves the brake held (never released on error) and
writes WCFU_BLOCKED with the reason.  Dying means "stays braked".
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

MK = Path("/root/mk_v2")
PY = "/root/miniconda3/bin/python"
RUNS = Path("/root/mk_v2_runs")
B9 = RUNS / "e3_b9_calib"
WC = RUNS / "e1" / "witness_confirmation"
LOG = B9 / "wcfu_chain.log"
LOCKF = B9 / "wcfu_chain.lock"
DONE = B9 / "WCFU_DONE"
BLOCKED = B9 / "WCFU_BLOCKED"
OWNER = "wc_followup"
KERNELS = ["L1_P39", "L1_P49", "L2_P68", "L2_P81",
           "L1_P94", "L2_P98", "L1_P96", "L2_P63"]
DTYPE_ERR = re.compile(r"Half|same dtype|expected scalar type")
POLL_S = 120


def log(msg):
    line = "[wcfu %s] %s" % (time.strftime("%Y-%m-%dT%H:%M:%S%z"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def sh(cmd, timeout=None):
    p = subprocess.run(cmd, shell=True, timeout=timeout,
                       capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def block(reason):
    BLOCKED.write_text(json.dumps(
        {"at": datetime.now().isoformat(), "reason": reason},
        ensure_ascii=False, indent=1), encoding="utf-8")
    log("BLOCKED: %s (brake stays held)" % reason)
    sys.exit(1)


def drivers_alive():
    # [_] keeps pgrep -f from matching this probe's own shell command line
    _, out = sh("pgrep -f '[_]b9_calib_driver_v2.py' | wc -l")
    return int(out.strip() or 0)


def gpu_apps():
    _, out = sh("nvidia-smi --query-compute-apps=pid --format=csv,noheader")
    return [l for l in out.splitlines() if l.strip()]


def load_queue():
    return json.loads((B9 / "queue_state.json").read_text(encoding="utf-8"))


def dtype_bug_units(qs):
    hits = []
    for unit, status in qs["done"].items():
        if status != "controls_incomplete" or "float16" not in unit:
            continue
        obs = sorted((B9 / "units" / unit).glob("*observations*.jsonl"))
        if not obs:
            continue
        reasons = []
        for line in open(obs[0], encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                if r.get("status") != "PASS":
                    reasons.append(str(r.get("reason") or ""))
        if reasons and all(DTYPE_ERR.search(x) for x in reasons):
            hits.append(unit)
    return sorted(hits)


def main():
    handle = open(LOCKF, "a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("another wcfu chain holds the lock -> exit")
        return 0
    handle.seek(0)
    handle.truncate()
    handle.write("%d\n" % os.getpid())
    handle.flush()
    if DONE.exists():
        log("WCFU_DONE already present -> nothing to do")
        return 0

    # step 1: wait for stage-1 to drain
    log("step 1: waiting for STAGE1_DONE + idle lanes/GPU")
    beats = 0
    while True:
        if (B9 / "STAGE1_DONE").exists() and drivers_alive() == 0 \
                and not gpu_apps():
            break
        beats += 1
        if beats % 15 == 0:
            log("step 1 heartbeat: stage1_done=%s drivers=%d gpu_apps=%d"
                % ((B9 / "STAGE1_DONE").exists(), drivers_alive(),
                   len(gpu_apps())))
        time.sleep(POLL_S)
    log("stage 1 drained")

    # step 2: signed brake
    rc, out = sh('%s %s/_b9_brake.py hold %s --reason '
                 '"WC-1 followup audit + fp16 fix wave (advisor plan '
                 '2026-07-31)" --release-when "wcfu chain releases after '
                 'the fix wave is queued"' % (PY, MK, OWNER))
    if rc != 0:
        block("brake hold failed: %s" % out[-400:])
    log("step 2: brake held by %s" % OWNER)

    # step 3: backups
    ts = time.strftime("%Y%m%dT%H%M%S")
    backup = WC / ("cells_backup_wcfu_" + ts)
    backup.mkdir(exist_ok=True)
    n = 0
    for f in (WC / "cells").glob("*.json"):
        if any(k in f.name for k in KERNELS):
            shutil.copy2(f, backup / f.name)
            n += 1
    shutil.copy2(WC / "wc1_report.json",
                 WC / ("wc1_report_pre_wcfu_%s.json" % ts))
    log("step 3: backed up %d cells + wc1_report" % n)

    # step 4: audit rerun (brake-derived pause marker satisfies _wc_audit)
    only = ",".join(KERNELS)
    log("step 4: audit --stage all --only %s --force --n-a 15" % only)
    rc, out = sh("cd %s && %s _wc_audit.py run --stage all --only %s "
                 "--force --n-a 15 --lane 0 --lanes 1" % (MK, PY, only),
                 timeout=6 * 3600)
    log("audit exit %d; tail: %s" % (rc, out[-300:].replace("\n", " | ")))
    if rc != 0:
        block("audit rc=%d" % rc)

    # step 5: regenerate the analysis
    rc, out = sh("cd %s && %s _wc_analyze.py > %s 2>&1"
                 % (MK, PY, WC / "wcfu_analyze_stdout.txt"), timeout=1800)
    if rc != 0:
        block("wc_analyze rc=%d" % rc)
    log("step 5: wc1_report regenerated")

    # step 6: fp16 patch
    src = MK / "scripts" / "run_e3_external.py"
    txt = src.read_text(encoding="utf-8")
    if "FP16FIX" in txt:
        log("step 6: patch already present")
    else:
        anchor = ("        candidate = self._instantiate("
                  "self.candidate_cls, init_seed)\n"
                  "        try:\n"
                  "            with torch.no_grad():")
        if txt.count(anchor) != 1:
            block("patch anchor count=%d" % txt.count(anchor))
        repl = ("        candidate = self._instantiate("
                "self.candidate_cls, init_seed)\n"
                "        if dtype_name != \"float32\" and "
                "hasattr(candidate, \"to\"):\n"
                "            # FP16FIX 2026-07-31: _case_inputs casts the "
                "inputs to the unit\n"
                "            # dtype but module parameters stayed float32, "
                "so every module\n"
                "            # with parameters failed with a dtype mismatch."
                "  Cast the\n"
                "            # candidate's floating params/buffers to the "
                "unit dtype too.\n"
                "            candidate = candidate.to("
                "getattr(torch, dtype_name))\n"
                "        try:\n"
                "            with torch.no_grad():")
        shutil.copy2(src, str(src) + ".bak_fp16fix")
        src.write_text(txt.replace(anchor, repl), encoding="utf-8")
        rc, out = sh("%s -m py_compile %s" % (PY, src))
        if rc != 0:
            shutil.copy2(str(src) + ".bak_fp16fix", src)
            block("patched file failed py_compile: %s" % out[-300:])
        log("step 6: FP16FIX applied")

    # step 7: canary
    qs = load_queue()
    buggy = dtype_bug_units(qs)
    log("step 7: %d dtype-bug units identified" % len(buggy))
    if not buggy:
        block("no dtype-bug units found -- unexpected")
    canary = "L2_P14__float16" if "L2_P14__float16" in buggy else buggy[0]
    spec = qs["units"][canary]
    scratch = B9 / "wcfu_canary"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir()
    rc, out = sh("cd %s && %s scripts/run_e3_external.py plan --baseline b9 "
                 "--subject-id %s --b9-dtypes %s --out %s/plan.json"
                 % (MK, PY, spec["task_key"], spec["dtype"], scratch),
                 timeout=600)
    if rc != 0:
        block("canary plan rc=%d: %s" % (rc, out[-300:]))
    rc, out = sh("cd %s && %s scripts/run_e3_external.py run "
                 "--plan %s/plan.json --task-module %s --candidate-module %s "
                 "--device cuda --allow-gpu --out-dir %s"
                 % (MK, PY, scratch, spec["task_file"], spec["task_file"],
                    scratch), timeout=1800)
    obs = sorted(scratch.glob("*observations*.jsonl"))
    bad = total = 0
    if obs:
        for line in open(obs[0], encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                total += 1
                if r.get("status") != "PASS" and \
                        DTYPE_ERR.search(str(r.get("reason") or "")):
                    bad += 1
    log("canary %s: rc=%d cases=%d dtype_errors=%d"
        % (canary, rc, total, bad))
    if rc != 0 or total == 0 or bad > 0:
        block("canary failed (rc=%d cases=%d dtype_errors=%d)"
              % (rc, total, bad))

    # step 8: requeue under the queue lock
    lock_handle = open(B9 / "queue_state.json.lock", "a+")
    fcntl.flock(lock_handle, fcntl.LOCK_EX)
    try:
        qs = load_queue()
        buggy = dtype_bug_units(qs)
        arch = B9 / "units_pre_fp16fix"
        arch.mkdir(exist_ok=True)
        shutil.copy2(B9 / "queue_state.json",
                     B9 / ("queue_state.json.bak_wcfu_" + ts))
        for unit in buggy:
            d = B9 / "units" / unit
            if d.exists():
                shutil.move(str(d), str(arch / unit))
            qs["done"].pop(unit, None)
            if unit not in qs["pending"]:
                qs["pending"].append(unit)
        qs["wave"] = "v2_stage1_fp16_fix"
        tmp = B9 / "queue_state.json.tmp"
        tmp.write_text(json.dumps(qs, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        os.replace(tmp, B9 / "queue_state.json")
    finally:
        fcntl.flock(lock_handle, fcntl.LOCK_UN)
        lock_handle.close()
    # scrub stale rows, completed lists and lane DONE markers
    for lane in (0, 1):
        rows = B9 / ("calibration_v2_lane%d.jsonl" % lane)
        if rows.exists():
            shutil.copy2(rows, str(rows) + ".bak_wcfu_" + ts)
            kept = []
            for line in open(rows, encoding="utf-8"):
                if not line.strip():
                    continue
                if json.loads(line).get("unit") in buggy:
                    continue
                kept.append(line if line.endswith("\n") else line + "\n")
            rows.write_text("".join(kept), encoding="utf-8")
        comp = B9 / ("completed_v2_lane%d.json" % lane)
        if comp.exists():
            try:
                names = json.loads(comp.read_text(encoding="utf-8"))
                if isinstance(names, list):
                    names = [u for u in names if u not in buggy]
                    comp.write_text(json.dumps(names, indent=1),
                                    encoding="utf-8")
            except Exception as exc:
                log("completed_v2_lane%d scrub skipped: %s" % (lane, exc))
        marker = B9 / ("B9_CALIB_V2_DONE_LANE%d" % lane)
        if marker.exists():
            marker.unlink()
    (B9 / "wcfu_fp16_requeue_manifest.json").write_text(
        json.dumps({"at": datetime.now().isoformat(),
                    "wave": "v2_stage1_fp16_fix", "units": buggy},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    log("step 8: requeued %d units as v2_stage1_fp16_fix" % len(buggy))

    # step 9: release brake, ensure the guard runs
    rc, out = sh("%s %s/_b9_brake.py release %s" % (PY, MK, OWNER))
    if rc != 0:
        block("brake release failed: %s" % out[-300:])
    log("step 9: brake released")
    time.sleep(30)
    _, out = sh("pgrep -f '[g]uard_b9_v2.sh' | wc -l")
    if int(out.strip() or 0) == 0:
        subprocess.Popen(
            "cd %s && setsid bash guard_b9_v2.sh > /dev/null 2>&1 "
            "< /dev/null &" % B9, shell=True)
        log("guard started")
    else:
        log("guard already alive")

    # step 10: wait for the fix wave to drain
    while True:
        time.sleep(POLL_S)
        try:
            qs = load_queue()
        except Exception:
            continue
        if not qs["pending"] and not qs.get("claimed") \
                and drivers_alive() == 0:
            break
    statuses = Counter(qs["done"].get(u) for u in buggy)
    DONE.write_text(json.dumps({
        "finished_at": datetime.now().isoformat(),
        "fix_wave_units": len(buggy),
        "fix_wave_statuses": dict(statuses),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    log("WCFU_DONE: %s" % dict(statuses))
    return 0


if __name__ == "__main__":
    sys.exit(main())
