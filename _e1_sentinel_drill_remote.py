"""Sandboxed drill for e1_sentinel.py: trigger every handbook rule once.

Runs on the A800: builds fake observation/checkpoint/plan files under
/root/mk_v2_runs/sentinel_drill/, re-points the sentinel module there and
sets DRY_RUN=True so no real process is killed, no real lane launched, and
no real observation/checkpoint file is touched.  File surgeries (requeue /
quarantine / plan reorder) run for real -- against the sandbox copies only.
"""
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, "/root/mk_v2")
import e1_sentinel as sent

SANDBOX = Path("/root/mk_v2_runs/sentinel_drill")
NOW = time.time()
PASSES = []


def setup_sandbox():
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)
    (SANDBOX / "e1").mkdir(parents=True)
    sent.RUNS = SANDBOX
    sent.E1 = SANDBOX / "e1"
    sent.DRY_RUN = True
    assert str(sent.obs_path(3)).startswith(str(SANDBOX)), "sandbox not active"


def rec(pid, outcome, **kw):
    r = {"probe_id": pid, "kernel": pid.split("__", 1)[0],
         "outcome": outcome, "inconclusive_class": None,
         "timed_out": False, "wall_ms": 1000.0}
    r.update(kw)
    return r


def write_lane(lane, records):
    sent.obs_path(lane).write_text(
        "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    sent.done_path(lane).write_text(
        json.dumps(sorted(r["probe_id"] for r in records)), encoding="utf-8")


def write_plan(lane_kernels):
    lanes = [{"lane": i, "kernels": lane_kernels.get(i, [])}
             for i in range(6)]
    sent.plan_path().write_text(json.dumps({"lanes": lanes}),
                                encoding="utf-8")


def fresh_state():
    return sent.default_state()


def snaps_from_sandbox(driver_pids=None, ages=None):
    procs = []          # empty proc table: sandbox has no lane drivers
    s = {l: sent.snapshot_lane(l, procs, NOW) for l in sent.LANES}
    for l in sent.LANES:
        if driver_pids and l in driver_pids:
            s[l]["driver_pid"] = driver_pids[l]
        if ages and l in ages:
            s[l]["obs_age_s"], s[l]["driver_age_s"] = ages[l]
    return s


def check(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"{name} {tag}{(' -- ' + detail) if detail else ''}")
    PASSES.append(bool(cond))
    if not cond:
        raise SystemExit(f"DRILL ABORT at {name}")


# --------------------------------------------------------------------- D1
def drill_rule1():
    setup_sandbox()
    good = [rec(f"L1_P1__op__{i}", "STILL_LIKELY_EQUIVALENT")
            for i in (0, 1)]
    tinc = [rec(f"L1_P2__op__{i}", "INCONCLUSIVE",
                inconclusive_class="timeout", timed_out=True)
            for i in (0, 1, 2)]
    write_lane(3, good + tinc)
    write_plan({3: ["L1_P1", "L1_P2"]})
    st = fresh_state()
    st["lanes"]["3"]["inc_hist"] = [[NOW - 3000, 0], [NOW, 3]]
    growth = sent.inc_growth(st["lanes"]["3"]["inc_hist"], NOW)
    check("D1a rule1-detection", growth >= sent.INC_THRESHOLD,
          f"timeout-INC growth={growth} in window")
    ev = {"actions": []}
    acted = sent.rule1_timeout_inc(st, snaps_from_sandbox(), ev, NOW)
    kept, _ = sent.parse_obs(3)
    archive = sent.E1 / "cse_observations_lane3_sentinel_requeue.jsonl"
    arch_n = len(archive.read_text().splitlines()) if archive.exists() else 0
    done = json.loads(sent.done_path(3).read_text())
    note = json.loads((sent.E1 / "sentinel_budget_overrides.json")
                      .read_text(encoding="utf-8"))
    check("D1b rule1-remediation",
          acted and len(kept) == 2 and arch_n == 3 and len(done) == 2
          and st["lanes"]["3"]["budget"] == 5400
          and note["overrides"][0]["timeout_s"] == 5400,
          f"obs 5->{len(kept)}, archived={arch_n}, completed 5->{len(done)}, "
          f"budget 3600->5400, manifest note written")
    ops = [a.get("op") for a in ev["actions"]]
    check("D1c rule1-restart-chain",
          ops[:1] == ["stop_guard"] and "requeue" in ops
          and "launch_lane" in ops and "start_guard" in ops,
          f"action chain={ops}")


# --------------------------------------------------------------------- D2
def drill_rule2():
    setup_sandbox()
    write_lane(3, [rec("L1_P1__op__0", "STILL_LIKELY_EQUIVALENT")])
    write_lane(4, [rec("L1_P9__op__0", "STILL_LIKELY_EQUIVALENT")])
    write_plan({3: ["L1_P1"], 4: ["L1_P9"]})
    s1, a1 = sent.decide_resource(120 * 2**30, 0, 0, 0)
    s2, a2 = sent.decide_resource(120 * 2**30, 0, 0, s1)
    s3, a3 = sent.decide_resource(50 * 2**30, 0, 0, s2)
    check("D2a rule2-state-machine",
          (s1, a1) == (1, "warn") and (s2, a2) == (2, "pause")
          and (s3, a3) == (0, None),
          "mem>110G: strike1=warn, strike2=pause, recovered=reset")
    st = fresh_state()
    ev = {"actions": []}
    acted = sent.rule2_resource(st, snaps_from_sandbox(), ev,
                                120 * 2**30, 0, 0)
    warn = json.loads(sent.warn_path().read_text(encoding="utf-8"))
    check("D2b rule2-first-strike-warn",
          not acted and st["res_streak"] == 1
          and warn["warnings"][-1]["kind"] == "rule2_resource_first_strike",
          "WARN written, lanes untouched")
    ev = {"actions": []}
    acted = sent.rule2_resource(st, snaps_from_sandbox(), ev,
                                120 * 2**30, 0, 0)
    ops = [a.get("op") for a in ev["actions"]]
    check("D2c rule2-pause-parallel",
          acted and st["paused_parallel"] is not None
          and "stop_guard" in ops,
          f"parallel lanes paused (queue intact), chain={ops}")
    ev = {"actions": []}
    acted = sent.rule2_resource(st, snaps_from_sandbox(), ev,
                                50 * 2**30, 0, 0)
    ops = [a.get("op") for a in ev["actions"]]
    check("D2d rule2-auto-resume",
          acted and st["paused_parallel"] is None and "start_guard" in ops,
          f"resources recovered -> guard restarted, chain={ops}")


# --------------------------------------------------------------------- D3
def drill_rule3():
    setup_sandbox()
    write_lane(3, [rec("L1_P1__op__0", "STILL_LIKELY_EQUIVALENT")])
    write_plan({3: ["L1_P1", "L1_P2", "L1_P3"]})
    check("D3a rule3-stall-truth-table",
          sent.is_stalled(10000, 20000, True)
          and not sent.is_stalled(10000, 120, True)
          and not sent.is_stalled(10000, 20000, False)
          and not sent.is_stalled(None, 20000, True),
          "stalled only when driver alive AND both clocks exceed 2.5h")
    orig_probe, orig_procs = sent.current_probe, sent.list_procs
    sent.current_probe = lambda procs, pid: "L1_P2__op__7"
    sent.list_procs = lambda: []
    try:
        st = fresh_state()
        ages = {3: (10000.0, 20000.0)}
        ev = {"actions": []}
        acted = sent.rule3_stall(st, snaps_from_sandbox({3: 99999}, ages), ev)
        kill1 = any(a.get("op") == "kill" or "lane3" in str(a)
                    for a in ev["actions"])
        check("D3b rule3-first-stall-kill",
              acted and st["lanes"]["3"]["last_stall_probe"]
              == "L1_P2__op__7",
              "hung driver killed (dry), probe remembered")
        st["actions"]["rule3_lane3"]["last_ts"] = 0     # lift cooldown
        ev = {"actions": []}
        acted = sent.rule3_stall(st, snaps_from_sandbox({3: 99999}, ages), ev)
        plan = json.loads(sent.plan_path().read_text())
        check("D3c rule3-same-probe-to-tail",
              acted and plan["lanes"][3]["kernels"] == ["L1_P1", "L1_P3",
                                                        "L1_P2"],
              f"kernel L1_P2 moved to queue tail: {plan['lanes'][3]['kernels']}")
    finally:
        sent.current_probe, sent.list_procs = orig_probe, orig_procs


# --------------------------------------------------------------------- D4
def drill_rule4():
    setup_sandbox()
    good_f = rec("L1_P5__op__0", "FALSIFIED", witness_policy="extreme_values",
                 witness_round=3, witness_seed=1234)
    bad_f = rec("L1_P5__op__1", "FALSIFIED", witness_policy="random",
                witness_round=2)          # witness_seed missing
    write_lane(4, [good_f, bad_f])
    write_plan({4: ["L1_P5"]})
    st = fresh_state()
    snaps = snaps_from_sandbox()
    check("D4a rule4-detection",
          [r["probe_id"] for r in snaps[4]["bad_witness"]]
          == ["L1_P5__op__1"],
          "good FALSIFIED kept, missing witness_seed flagged")
    ev = {"actions": []}
    acted = sent.rule4_quality(st, snaps, ev)
    kept, _ = sent.parse_obs(4)
    q = sent.E1 / "cse_observations_lane4_quarantine.jsonl"
    warn = json.loads(sent.warn_path().read_text(encoding="utf-8"))
    check("D4b rule4-quarantine",
          acted and [r["probe_id"] for r in kept] == ["L1_P5__op__0"]
          and q.exists() and len(q.read_text().splitlines()) == 1
          and json.loads(sent.done_path(4).read_text())
          == ["L1_P5__op__0"]
          and warn["warnings"][-1]["kind"] == "rule4_quality_quarantine"
          and st["quarantine_counts"]["L1_P5__op__1"] == 1,
          "record quarantined + probe requeued + WARN 高亮, 其余照跑")


# --------------------------------------------------------------------- D5
def drill_rule5():
    setup_sandbox()
    tinc = [rec(f"L1_P2__op__{i}", "INCONCLUSIVE",
                inconclusive_class="timeout", timed_out=True)
            for i in (0, 1, 2)]
    write_lane(3, tinc)
    write_plan({3: ["L1_P2"]})
    st = fresh_state()
    st["lanes"]["3"]["inc_hist"] = [[NOW - 3000, 0], [NOW, 3]]
    st["actions"]["rule1_lane3"] = {"count": 2, "fails": 1, "last_ts": 0}
    ev = {"actions": []}
    sent.rule1_timeout_inc(st, snaps_from_sandbox(), ev, NOW)
    halt = json.loads(sent.halt_path().read_text(encoding="utf-8"))
    check("D5a fallback-halt-after-2-failed-attempts",
          halt["reason"] == "rule1_escalation_ineffective_twice",
          f"third trigger after 2 attempts -> HALT: {halt['reason']}")
    before = sent.halt_path().read_text()
    sent.do_halt(st, "other_reason", {}, {"actions": []})
    check("D5b halt-idempotent",
          sent.halt_path().read_text() == before,
          "existing ANOMALY_HALT.json never overwritten")

    setup_sandbox()   # integrity sub-drill
    write_lane(3, [rec("L1_P1__op__0", "STILL_LIKELY_EQUIVALENT")])
    write_plan({3: ["L1_P1"]})
    st = fresh_state()
    ev = {"actions": []}
    halted = sent.integrity_check(st, snaps_from_sandbox(), ev)   # baseline
    dup = rec("L1_P1__op__0", "STILL_LIKELY_EQUIVALENT")
    with open(sent.obs_path(3), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(dup) + "\n")
    halted1 = sent.integrity_check(st, snaps_from_sandbox(), ev)
    halted2 = sent.integrity_check(st, snaps_from_sandbox(), ev)
    check("D5c integrity-two-cycle-halt",
          not halted and not halted1 and halted2
          and sent.halt_path().exists()
          and json.loads(sent.halt_path().read_text(encoding="utf-8"))
          ["reason"] == "integrity_breakage_unrecoverable_by_requeue",
          "duplicate checkpoint id: warn on cycle1, HALT on cycle2")


if __name__ == "__main__":
    for d in (drill_rule1, drill_rule2, drill_rule3, drill_rule4,
              drill_rule5):
        d()
    shutil.rmtree(SANDBOX, ignore_errors=True)
    print(f"DRILL_ALL_PASS ({len(PASSES)} checks)")
