"""WC-1 analysis v2 -- runs locally against a pulled copy of the audit output.

Differences from the shipped _wc_analyze.py, each of which is a defect fix
rather than a protocol change (documented in the report):

 1. The sufficiency bar for a control unit is n_A x stress_repeats for a stress
    position but only n_A for a random position, because the plan provisions
    exactly n_A rounds there.  The shipped script uses a flat 20 and therefore
    parks every random-position witness at PENDING_CONTROL forever.
 2. "control has no divergence but too few clean rounds" is separated from
    "control diverged": the former is an infrastructure outcome (worker budget
    exhausted / CUDA OOM) and carries no evidence about the kernel.
 3. Candidate replays are counted only at the witness (policy, sub_index), not
    over every stress round of the cell, so j is a replay index.
 4. cells_done counts planned cells only; files left over from the superseded
    single-lane plan are reported separately instead of inflating coverage.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

D = Path("_wc_remote")
CELLS = D / "cells"

VOID = "void"
CONFIRMED = "confirmed"
REFUTED = "refuted"
CTRL_INC = "control_inconclusive"
CAND_INC = "candidate_inconclusive"
PEND_CTRL = "pending_control_not_run"
PEND_CAND = "pending_candidate_not_run"
OOS = "out_of_scope_non_numeric"


def load(name):
    return json.loads((D / name).read_text(encoding="utf-8"))


def load_cells():
    out = {}
    for p in sorted(CELLS.glob("*.json")):
        try:
            out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            print("!! unreadable cell %s: %r" % (p.stem, exc))
    return out


def pos_key(policy):
    return str(policy)


def analyse():
    inv = load("_wc_witness_inventory.json")
    plan = load("plan.json")
    cells = load_cells()
    proto = plan["protocol"]
    n_a, n_b = proto["n_A"], proto["n_B"]

    planned_ids = ({c["cell_id"] for c in plan["control_cells"]}
                   | {c["cell_id"] for c in plan["confirm_cells"]})
    stale = sorted(set(cells) - planned_ids)

    # ---------------- control units ----------------
    control = {}
    for cell in plan["control_cells"]:
        rec = cells.get(cell["cell_id"])
        stage_proto = proto["cse" if cell["stage"] == "cse" else "equiv"]
        reps = stage_proto["stress_repeats"]
        is_random = any(p == "__random__" for p, _ in cell["positions"])
        required = n_a if is_random else n_a * reps
        key = (cell["kernel"], cell["stage"],
               pos_key("__random__" if is_random else cell["positions"][0][0]))

        info = {
            "cell_id": cell["cell_id"], "kernel": cell["kernel"],
            "stage": cell["stage"], "policy": key[2], "is_random": is_random,
            "required_rounds": required, "planned_rounds": cell["rounds"],
            "probe_ids": cell.get("probe_ids") or [],
            "witness_sub_indices": cell.get("witness_sub_indices"),
            "n_pass": 0, "n_fail": 0, "n_inconclusive": 0, "n_other": 0,
            "by_sub": {}, "first_fail_at": None, "fail_seed": None,
            "fail_sub_index": None, "max_abs_error": None,
            "validation_status": None, "timed_out": None, "wall_s": None,
            "budget_s": None, "why_short": None, "state": "NOT_RUN",
        }
        if rec is None:
            control[key] = info
            continue
        info.update(validation_status=rec.get("validation_status"),
                    timed_out=rec.get("timed_out"), wall_s=rec.get("wall_s"),
                    budget_s=rec.get("worker_budget_s"))
        seq = [r for r in rec["rounds"]
               if (r.get("round_type") == "random") == is_random]
        for i, r in enumerate(seq, 1):
            st = r.get("status")
            sub = ("rand%s" % r.get("round_index") if is_random
                   else "si%s/seed%s" % (r.get("sub_index"), r.get("seed")))
            slot = info["by_sub"].setdefault(sub, Counter())
            slot[st] += 1
            if st == "pass":
                info["n_pass"] += 1
            elif st == "fail":
                info["n_fail"] += 1
                if info["first_fail_at"] is None:
                    info["first_fail_at"] = i
                    info["fail_seed"] = r.get("seed")
                    info["fail_sub_index"] = r.get("sub_index")
                    info["max_abs_error"] = r.get("max_abs_error")
            elif st == "inconclusive":
                info["n_inconclusive"] += 1
            else:
                info["n_other"] += 1

        if info["n_fail"] > 0:
            info["state"] = "DIVERGED"
        elif info["n_pass"] >= required:
            info["state"] = "STABLE"
        else:
            info["state"] = "INSUFFICIENT"
            if rec.get("timed_out"):
                info["why_short"] = ("worker budget %ss exhausted after %ss with "
                                     "%d/%d clean rounds"
                                     % (rec.get("worker_budget_s"), rec.get("wall_s"),
                                        info["n_pass"], required))
            elif info["n_inconclusive"]:
                err = ((rec.get("errors") or [{}])[0].get("exception_type")
                       or "resource limit")
                info["why_short"] = ("%d/%d rounds hit %s (infrastructure), "
                                     "%d clean rounds"
                                     % (info["n_inconclusive"], len(seq), err,
                                        info["n_pass"]))
            else:
                info["why_short"] = ("only %d/%d clean rounds recorded"
                                     % (info["n_pass"], required))
        control[key] = info

    # ---------------- candidate cells ----------------
    confirm = {}
    for cell in plan["confirm_cells"]:
        rec = cells.get(cell["cell_id"])
        pos = cell["position"]
        is_random = pos["round_type"] != "stress"
        info = {"cell_id": cell["cell_id"], "probe_id": cell["probe_id"],
                "planned_replays": cell["replays"], "is_random": is_random,
                "n_replays": 0, "n_pass": 0, "n_fail": 0, "n_inconclusive": 0,
                "j": None, "max_abs_error": None, "state": "NOT_RUN",
                "validation_status": None, "timed_out": None, "wall_s": None}
        if rec is None:
            confirm[cell["probe_id"]] = info
            continue
        info.update(validation_status=rec.get("validation_status"),
                    timed_out=rec.get("timed_out"), wall_s=rec.get("wall_s"))
        if is_random:
            seq = [r for r in rec["rounds"]
                   if r.get("round_type") == "random"
                   and r.get("round_index") == pos.get("round_index")]
        else:
            # The seed is the identity of a round position.  Under the seed
            # shortcut the replay carries sub_index 0 while reproducing the
            # witness seed, so matching on sub_index would drop every si>0 cell.
            seq = [r for r in rec["rounds"]
                   if r.get("round_type") == "stress"
                   and r.get("policy") == pos.get("policy")
                   and r.get("seed") == pos.get("seed")]
        info["n_replays"] = len(seq)
        for i, r in enumerate(seq, 1):
            st = r.get("status")
            if st == "pass":
                info["n_pass"] += 1
            elif st == "fail":
                info["n_fail"] += 1
                if info["j"] is None:
                    info["j"] = i
                    info["max_abs_error"] = r.get("max_abs_error")
            elif st == "inconclusive":
                info["n_inconclusive"] += 1

        if info["n_fail"] > 0:
            info["state"] = "REPRODUCED"
        elif rec.get("timed_out") or rec.get("validation_status") is None:
            info["state"] = "WORKER_FAILURE"
        elif info["n_pass"] >= info["planned_replays"]:
            info["state"] = "NOT_REPRODUCED"
        elif info["n_pass"] > 0:
            info["state"] = "PARTIAL_NOT_REPRODUCED"
        else:
            info["state"] = "NO_EVIDENCE"
        confirm[cell["probe_id"]] = info

    # ---------------- per-witness verdicts ----------------
    verdicts = []
    for rec in inv:
        d = rec.get("divergence") or {}
        base = {k: rec[k] for k in
                ("stage", "probe_id", "kernel", "operator", "fault_class")}
        if d.get("round_type") is None:
            verdicts.append({**base, "position": None, "verdict": OOS,
                             "why": "witness is not a numeric round divergence",
                             "control": None, "candidate": None})
            continue
        is_random = d.get("round_type") != "stress"
        key = (rec["kernel"], rec["stage"],
               pos_key("__random__" if is_random else d.get("policy")))
        ctrl = control.get(key)
        cand = confirm.get(rec["probe_id"])

        if ctrl is None or ctrl["state"] == "NOT_RUN":
            verdict, why = PEND_CTRL, "control cell has not run yet"
        elif ctrl["state"] == "DIVERGED":
            verdict = VOID
            at_seed = {kk: dict(vv) for kk, vv in ctrl["by_sub"].items()
                       if kk.endswith("seed%s" % d.get("seed"))}
            same_seed = ctrl["fail_seed"] == d.get("seed")
            why = ("control diverged at replay %s (%s/si%s/seed%s, "
                   "max_abs_error=%s); witness seed %s -> control evidence %s; "
                   "divergence is %s the witness seed, void follows the "
                   "pre-registered pooling of control evidence over the policy"
                   % (ctrl["first_fail_at"], ctrl["policy"],
                      ctrl["fail_sub_index"], ctrl["fail_seed"],
                      ctrl["max_abs_error"], d.get("seed"), at_seed or "none",
                      "at" if same_seed else "NOT at"))
        elif ctrl["state"] == "INSUFFICIENT":
            verdict, why = CTRL_INC, "control not decidable: " + (ctrl["why_short"] or "")
        elif cand is None or cand["state"] == "NOT_RUN":
            verdict, why = PEND_CAND, "candidate cell has not run yet"
        elif cand["state"] == "REPRODUCED":
            verdict = CONFIRMED
            why = ("control clean %d/%d; witness reproduced on replay %d of %d "
                   "(max_abs_error=%s)"
                   % (ctrl["n_pass"], ctrl["required_rounds"], cand["j"],
                      cand["planned_replays"], cand["max_abs_error"]))
        elif cand["state"] in ("WORKER_FAILURE", "NO_EVIDENCE"):
            verdict = CAND_INC
            why = ("control clean %d/%d but candidate produced no usable replay "
                   "(state=%s, timed_out=%s)"
                   % (ctrl["n_pass"], ctrl["required_rounds"], cand["state"],
                      cand["timed_out"]))
        elif cand["state"] == "PARTIAL_NOT_REPRODUCED":
            verdict = CAND_INC
            why = ("control clean %d/%d; only %d/%d candidate replays usable "
                   "(%d inconclusive) and none reproduced"
                   % (ctrl["n_pass"], ctrl["required_rounds"], cand["n_pass"],
                      cand["planned_replays"], cand["n_inconclusive"]))
        else:
            verdict = REFUTED
            why = ("control clean %d/%d; %d/%d candidate replays all passed -- "
                   "the production witness was not reproducible"
                   % (ctrl["n_pass"], ctrl["required_rounds"], cand["n_pass"],
                      cand["planned_replays"]))
        verdicts.append({**base,
                         "position": {k: d.get(k) for k in
                                      ("round_type", "policy", "sub_index",
                                       "round_index", "seed")},
                         "verdict": verdict, "why": why,
                         "control_key": "%s|%s|%s" % key, "control": ctrl,
                         "candidate": cand,
                         "valid_rounds_in_production": rec.get("valid_rounds")})

    return {"protocol": proto, "plan": plan, "cells": cells, "stale": stale,
            "planned_ids": planned_ids, "control": control,
            "confirm": confirm, "verdicts": verdicts}


def report(a):
    proto, verdicts, control = a["protocol"], a["verdicts"], a["control"]
    plan = a["plan"]
    have = len(set(a["cells"]) & a["planned_ids"])
    print("=== coverage ===")
    print("protocol %s n_A=%d n_B=%d k=%d round_timeout=%ds"
          % (proto["id"], proto["n_A"], proto["n_B"], proto["k"],
             proto["round_timeout_s"]))
    print("planned cells %d (control %d + confirm %d); present %d; stale %d %s"
          % (len(a["planned_ids"]), len(plan["control_cells"]),
             len(plan["confirm_cells"]), have, len(a["stale"]), a["stale"]))
    ctrl_have = sum(1 for c in control.values() if c["state"] != "NOT_RUN")
    print("control units %d, run %d" % (len(control), ctrl_have))
    print("control states:", dict(Counter(c["state"] for c in control.values())))

    print("\n=== (a) kernel determinism, per control unit ===")
    print("%-46s %-13s %5s %5s %5s %6s  %s"
          % ("control unit", "state", "pass", "fail", "inc", "flake", "note"))
    for k in sorted(control, key=lambda x: (x[0], x[1], x[2])):
        c = control[k]
        n = c["n_pass"] + c["n_fail"]
        flake = ("%.3f" % (c["n_fail"] / n)) if n else "n/a"
        print("%-46s %-13s %5d %5d %5d %6s  %s"
              % (c["cell_id"], c["state"], c["n_pass"], c["n_fail"],
                 c["n_inconclusive"], flake, c["why_short"] or ""))

    print("\n--- unstable / undecidable control units only ---")
    for k in sorted(control):
        c = control[k]
        if c["state"] == "STABLE":
            continue
        print("  %-46s %-13s pass=%d fail=%d inc=%d by_sub=%s"
              % (c["cell_id"], c["state"], c["n_pass"], c["n_fail"],
                 c["n_inconclusive"],
                 {kk: dict(vv) for kk, vv in c["by_sub"].items()}))
        print("      probes: %s" % ", ".join(c["probe_ids"]))
        if c["state"] == "DIVERGED":
            print("      first fail at replay %s, si=%s seed=%s max_abs_error=%s"
                  % (c["first_fail_at"], c["fail_sub_index"], c["fail_seed"],
                     c["max_abs_error"]))
        if c["why_short"]:
            print("      why: %s" % c["why_short"])

    print("\n=== (b) witness verdicts ===")
    counts = Counter(v["verdict"] for v in verdicts)
    for k in sorted(counts):
        print("  %-28s %d" % (k, counts[k]))
    for stage in ("cse", "equiv"):
        rows = [v for v in verdicts if v["stage"] == stage]
        print("  %-6s n=%-3d %s" % (stage, len(rows),
                                    dict(Counter(v["verdict"] for v in rows))))

    print("\n--- per witness ---")
    for v in sorted(verdicts, key=lambda x: (x["stage"], x["verdict"], x["probe_id"])):
        p = v["position"]
        print("  [%-5s] %-34s %-9s %-24s %s"
              % (v["stage"], v["probe_id"], v["fault_class"], v["verdict"],
                 ("%s/si%s/ri%s" % (p["policy"], p["sub_index"], p["round_index"]))
                 if p else "-"))
        print("           %s" % v["why"])

    print("\n=== fault-class coverage ===")
    for stage in ("cse", "equiv"):
        rows = [v for v in verdicts if v["stage"] == stage]
        before = Counter(v["fault_class"] for v in rows)
        kept = [v for v in rows if v["verdict"] == CONFIRMED]
        after = Counter(v["fault_class"] for v in kept)
        undec = [v for v in rows if v["verdict"] in
                 (CTRL_INC, CAND_INC, PEND_CTRL, PEND_CAND)]
        print("  %s before: %d probes / %d classes %s"
              % (stage, len(rows), len(before), dict(before)))
        print("  %s confirmed: %d probes / %d classes %s"
              % (stage, len(kept), len(after), dict(after)))
        print("  %s still undecided: %d %s"
              % (stage, len(undec), dict(Counter(v["fault_class"] for v in undec))))
        lost = sorted(set(before) - set(after))
        print("  %s classes with zero confirmed probes: %s" % (stage, lost))
    return counts


if __name__ == "__main__":
    report(analyse())
