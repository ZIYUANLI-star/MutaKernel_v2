#!/usr/bin/env python3
"""WC-1 analysis: per-kernel determinism verdicts, per-witness confirmation
verdicts, and the resulting ledger deltas.  Read-only w.r.t. the E1 ledger."""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from math import comb
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")
OUTDIR = E1 / "witness_confirmation"
CELLS = OUTDIR / "cells"

CSE_MIN_VALID_ROUNDS = 77
CSE_MIN_RANDOM_PASS = 30
CSE_MIN_STRESS_ROUNDS = 42
EQUIV_MIN_STRESS_ROUNDS = 8
# WC-1 criterion (a): a control unit is decided once it has accumulated this
# many clean rounds at the witness policy (n_A = 10 replays x production
# stress_repeats 2 or 3).
MIN_CONTROL_ROUNDS = 20


def load_round_counts():
    path = E1 / "_wc_round_counts.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


ROUND_COUNTS = load_round_counts()


def load_cells():
    out = {}
    for path in sorted(CELLS.glob("*.json")):
        out[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return out


def pos_key(policy, sub_index):
    """The control unit key.  Kernel nondeterminism is a property of the input
    distribution a policy induces, so control evidence is pooled over the
    production sub_index range of that policy (see WC-1 pre-registration)."""
    return str(policy)


def main():
    inv = json.loads((E1 / "_wc_witness_inventory.json").read_text(encoding="utf-8"))
    plan = json.loads((OUTDIR / "plan.json").read_text(encoding="utf-8"))
    cells = load_cells()

    # ---- criterion (a): control verdict per (kernel, stage, position) ----
    control = {}
    control_cell_state = {}
    for cell in plan["control_cells"]:
        rec = cells.get(cell["cell_id"])
        state = "MISSING"
        if rec is not None:
            n_fail = sum(1 for r in rec["rounds"] if r["status"] == "fail")
            n_pass = sum(1 for r in rec["rounds"] if r["status"] == "pass")
            if n_fail or rec.get("divergence"):
                state = "DIVERGED"
            elif rec.get("timed_out") or rec.get("validation_status") is None:
                # A truncated cell still contributes its executed clean rounds;
                # sufficiency is decided per unit below, not by the exit status.
                state = "TRUNCATED_CLEAN" if n_pass else "WORKER_FAILURE"
            elif rec.get("validation_status") == "pass":
                state = "CLEAN"
            else:
                state = "PARTIAL_%s" % rec.get("validation_status")
        control_cell_state[cell["cell_id"]] = state
        # per-position pass counts read out of the trials
        counts = defaultdict(lambda: [0, 0])   # key -> [pass, fail]
        if rec:
            for r in rec["rounds"]:
                if r["round_type"] == "stress":
                    key = pos_key(r["policy"], r["sub_index"])
                else:
                    key = pos_key("__random__", r["round_index"])
                slot = counts[key]
                if r["status"] == "pass":
                    slot[0] += 1
                elif r["status"] == "fail":
                    slot[1] += 1
        for policy, sub_index in cell["positions"]:
            key = (cell["kernel"], cell["stage"], pos_key(policy, sub_index))
            if key in control:
                continue
            c = counts.get(pos_key(policy, sub_index), [0, 0])
            if policy == "__random__":
                c = [sum(v[0] for k, v in counts.items() if k == "__random__"),
                     sum(v[1] for k, v in counts.items() if k == "__random__")]
            control[key] = {
                "cell_id": cell["cell_id"], "cell_state": state,
                "pass_rounds": c[0], "fail_rounds": c[1],
                "planned_replays": cell["replays"],
                "planned_rounds": cell["rounds"],
                "witness_sub_indices": cell.get("witness_sub_indices"),
            }

    # ---- criterion (b): candidate verdict per witness ----
    confirm = {}
    for cell in plan["confirm_cells"]:
        rec = cells.get(cell["cell_id"])
        j = None
        state = "MISSING"
        if rec is not None:
            if rec.get("timed_out") or rec.get("validation_status") is None:
                state = "WORKER_FAILURE"
            else:
                stress = [r for r in rec["rounds"] if r["round_type"] == "stress"]
                rnd = [r for r in rec["rounds"] if r["round_type"] == "random"]
                seq = stress if cell["position"]["round_type"] == "stress" else rnd
                for i, r in enumerate(seq, 1):
                    if r["status"] == "fail":
                        j = i
                        break
                state = "REPRODUCED" if j is not None else "NOT_REPRODUCED"
        confirm[cell["probe_id"]] = {
            "cell_id": cell["cell_id"], "state": state, "j": j,
            "planned_replays": cell["replays"],
            "max_abs_error": (rec or {}).get("divergence", {}).get("oracle", {}) and None,
            "rounds_executed": len((rec or {}).get("rounds") or []),
        }

    # ---- combine ----
    verdicts = []
    for rec in inv:
        d = rec.get("divergence") or {}
        if d.get("round_type") is None:
            verdicts.append({**{k: rec[k] for k in
                               ("stage", "probe_id", "kernel", "operator", "fault_class")},
                             "position": None, "verdict": "OUT_OF_SCOPE_NON_NUMERIC",
                             "control": None, "candidate": None})
            continue
        if d.get("round_type") == "stress":
            key = (rec["kernel"], rec["stage"], pos_key(d.get("policy"), d.get("sub_index")))
        else:
            key = (rec["kernel"], rec["stage"], pos_key("__random__", d.get("round_index")))
        ctrl = control.get(key)
        cand = confirm.get(rec["probe_id"])
        min_ctrl = MIN_CONTROL_ROUNDS
        if ctrl is None:
            verdict = "PENDING_CONTROL"
        elif ctrl["fail_rounds"] == 0 and ctrl["pass_rounds"] < min_ctrl:
            verdict = "PENDING_CONTROL"
        elif ctrl["fail_rounds"] > 0:
            verdict = "NON_DISCRIMINATING"
        elif cand is None or cand["state"] in ("MISSING", "WORKER_FAILURE"):
            verdict = "PENDING_CANDIDATE"
        elif cand["state"] == "NOT_REPRODUCED":
            verdict = "UNCONFIRMED"
        elif cand["j"] == 1:
            verdict = "CONFIRMED"
        else:
            verdict = "ESCALATED"
        verdicts.append({
            "stage": rec["stage"], "probe_id": rec["probe_id"], "kernel": rec["kernel"],
            "operator": rec["operator"], "fault_class": rec["fault_class"],
            "position": {k: d.get(k) for k in
                         ("round_type", "policy", "sub_index", "round_index", "seed")},
            "verdict": verdict, "control": ctrl, "candidate": cand,
            "valid_rounds_in_production": rec.get("valid_rounds"),
        })

    # ---- kernel-level determinism table ----
    kernel_table = {}
    for (kernel, stage, key), ctrl in sorted(control.items()):
        row = kernel_table.setdefault(kernel, {"positions": [], "nondeterministic": False,
                                              "audited_positions": 0})
        row["positions"].append({
            "stage": stage, "position": key, "cell_state": ctrl["cell_state"],
            "pass_rounds": ctrl["pass_rounds"], "fail_rounds": ctrl["fail_rounds"],
            "flake_rate": (ctrl["fail_rounds"] /
                           max(1, ctrl["pass_rounds"] + ctrl["fail_rounds"])),
        })
        if ctrl["fail_rounds"] > 0:
            row["nondeterministic"] = True
        if ctrl["fail_rounds"] > 0 or ctrl["pass_rounds"] >= MIN_CONTROL_ROUNDS:
            row["audited_positions"] += 1
    for row in kernel_table.values():
        row["status"] = ("NONDETERMINISTIC" if row["nondeterministic"] else
                         "deterministic" if row["audited_positions"] == len(row["positions"])
                         else "incomplete")

    # ---- ledger impact ----
    def bucket(stage):
        rows = [v for v in verdicts if v["stage"] == stage]
        return Counter(v["verdict"] for v in rows), rows

    cse_counts, cse_rows = bucket("cse")
    eq_counts, eq_rows = bucket("equiv")

    def survivors(rows):
        return [v for v in rows if v["verdict"] in ("CONFIRMED", "CONFIRMED_INTERMITTENT")]

    cse_keep = survivors(cse_rows)
    eq_keep = survivors(eq_rows)

    # Re-grading of voided probes against the UNCHANGED production thresholds.
    # WC-1 section 2.7: drop the voided round from the evidence (it counts
    # neither as a valid round nor as a kill), then re-apply the existing
    # grading function to what is left.  The production run stops at the
    # divergence, so the remaining evidence is exactly that record's own
    # passing rounds -- no re-run is needed to test the thresholds.
    regrade = []
    for v in cse_rows + eq_rows:
        if v["verdict"] not in ("NON_DISCRIMINATING", "UNCONFIRMED"):
            continue
        counts = ROUND_COUNTS.get(v["probe_id"], {})
        rp, sp = counts.get("random_pass", 0), counts.get("stress_pass", 0)
        vr = v.get("valid_rounds_in_production")
        if v["stage"] == "cse":
            ok = (vr is not None and vr >= CSE_MIN_VALID_ROUNDS
                  and rp >= CSE_MIN_RANDOM_PASS and sp >= CSE_MIN_STRESS_ROUNDS)
            need = ("valid>=%d and random_pass>=%d and stress_pass>=%d"
                    % (CSE_MIN_VALID_ROUNDS, CSE_MIN_RANDOM_PASS,
                       CSE_MIN_STRESS_ROUNDS))
        else:
            ok = sp >= EQUIV_MIN_STRESS_ROUNDS
            need = "stress_pass>=%d" % EQUIV_MIN_STRESS_ROUNDS
        regrade.append({
            "stage": v["stage"], "probe_id": v["probe_id"], "kernel": v["kernel"],
            "fault_class": v["fault_class"], "voided_because": v["verdict"],
            "valid_rounds_in_production": vr,
            "random_pass": rp, "stress_pass": sp, "threshold": need,
            "regrade": ("STILL_LIKELY_EQUIVALENT" if v["stage"] == "cse"
                        else "LIKELY_EQUIVALENT") if ok
                       else "REQUEUE_THEN_KERNEL_UNDECIDABLE_IF_UNCLOSABLE",
        })

    report = {
        "protocol": plan["protocol"],
        "generated_at": datetime.now().isoformat(),
        "cells_done": len(cells),
        "cells_planned": len(plan["control_cells"]) + len(plan["confirm_cells"]),
        "control_cell_states": dict(Counter(control_cell_state.values())),
        "kernel_determinism": kernel_table,
        "nondeterministic_kernels": sorted(k for k, v in kernel_table.items()
                                           if v["nondeterministic"]),
        "verdicts": verdicts,
        "verdict_counts": {"cse": dict(cse_counts), "equiv": dict(eq_counts)},
        "final_counts": {
            "cse_FALSIFIED_before": sum(1 for v in cse_rows),
            "cse_FALSIFIED_after": len(cse_keep),
            "equiv_WITNESSED_before": sum(1 for v in eq_rows),
            "equiv_WITNESSED_after": len(eq_keep) + sum(
                1 for v in eq_rows if v["verdict"] == "OUT_OF_SCOPE_NON_NUMERIC"),
        },
        "cse_fault_classes_before": dict(Counter(v["fault_class"] for v in cse_rows)),
        "cse_fault_classes_after": dict(Counter(v["fault_class"] for v in cse_keep)),
        "equiv_fault_classes_before": dict(Counter(v["fault_class"] for v in eq_rows)),
        "equiv_fault_classes_after": dict(Counter(
            v["fault_class"] for v in eq_keep
            + [v for v in eq_rows if v["verdict"] == "OUT_OF_SCOPE_NON_NUMERIC"])),
        "regrade_plan": regrade,
    }
    (OUTDIR / "wc1_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print("cells %d/%d ; control cell states: %s"
          % (report["cells_done"], report["cells_planned"],
             report["control_cell_states"]))
    print("\n=== kernel determinism ===")
    for k in sorted(kernel_table):
        v = kernel_table[k]
        print("  %-8s %-17s %s" % (k, v["status"],
              " | ".join("%s/%s %s p=%d f=%d" % (p["stage"], p["position"],
                                                 p["cell_state"], p["pass_rounds"],
                                                 p["fail_rounds"])
                         for p in v["positions"])))
    print("\n=== verdicts ===")
    print("  cse  :", dict(cse_counts))
    print("  equiv:", dict(eq_counts))
    print("\n=== final counts ===", json.dumps(report["final_counts"]))
    print("cse fault classes before:", report["cse_fault_classes_before"])
    print("cse fault classes after :", report["cse_fault_classes_after"])
    print("\n=== non-confirmed witnesses ===")
    for v in verdicts:
        if v["verdict"] not in ("CONFIRMED",):
            print("  [%s] %-34s %-9s %s pos=%s" % (
                v["stage"], v["probe_id"], v["fault_class"], v["verdict"],
                v["position"] and "%s/si%s/seed%s" % (v["position"]["policy"],
                                                      v["position"]["sub_index"],
                                                      v["position"]["seed"])))
    print("\n=== regrade plan ===")
    for r in report["regrade_plan"]:
        print("  ", json.dumps(r, ensure_ascii=False))
    print("\nwrote", OUTDIR / "wc1_report.json")


if __name__ == "__main__":
    main()
