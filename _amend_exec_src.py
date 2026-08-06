#!/usr/bin/env python3
"""One-shot auditable E1 ledger amendment (WC-1 closure), 2026-08-01.

Basis:
  * wc1_report.json (generated 2026-08-01T07:33) verdicts + regrade_plan
  * advisor ruling WC1_20260731 (rulings 1-3)
  * requeue_final/observations.jsonl (the 7 REQUEUE_THEN_GRADE outcomes)

Actions (each applied to the live ledger with the original row archived):
  equiv_observations.jsonl:
    - L1_P37__index_replace__11: WITNESSED -> LIKELY_EQUIVALENT (direct,
      net stress 10>=8 after voiding poisoned-position witness)
    - L1_P37__const_perturb__{2,3,7}, L1_P37__mask_boundary__0,
      L1_P49__sync_remove__0, L2_P63__sync_remove__1: replaced by the
      requeue_final outcome row (production protocol, poisoned positions
      excluded for P37)
    - L2_P68__relop_replace__3, L2_P98__mask_boundary__3: verdict kept
      WITNESSED, annotated intermittent (preregistered rule >=2 merged
      reproductions)
  cse_observations_lane3_signoff_requeue.jsonl:
    - L1_P37__sync_remove__1: FALSIFIED -> STILL_LIKELY_EQUIVALENT (direct,
      99 net valid rounds >= thresholds after voiding witness)
  cse_observations_lane3.jsonl:
    - L1_P96__relop_replace__8: replaced by requeue_final outcome
    - L1_P94__const_perturb__7: kept FALSIFIED, annotated intermittent

Every change is recorded in e1/amendment_v1/amendment_manifest.json with
before/after and basis.  Archived originals go to
e1/amendment_v1/archived_rows.jsonl.
"""
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")
OUT = E1 / "amendment_v1"
OUT.mkdir(parents=True, exist_ok=True)
RQ = E1 / "requeue_final"

TS = datetime.now().strftime("%Y%m%dT%H%M%S")


def now():
    return datetime.now(timezone.utc).isoformat()


def load_requeue():
    rows = {}
    for line in open(RQ / "observations.jsonl", encoding="utf-8"):
        r = json.loads(line)
        rows[r["probe_id"]] = r  # latest wins
    return rows


def main():
    if not (RQ / "RQ7_DONE").exists():
        raise SystemExit("requeue not finished; refusing to amend")
    rq = load_requeue()
    need = ["L1_P37__const_perturb__2", "L1_P37__const_perturb__3",
            "L1_P37__const_perturb__7", "L1_P37__mask_boundary__0",
            "L1_P49__sync_remove__0", "L2_P63__sync_remove__1",
            "L1_P96__relop_replace__8"]
    missing = [p for p in need if p not in rq]
    if missing:
        raise SystemExit("requeue outcomes missing: %r" % missing)

    changes = []
    archived = []

    def note_change(file, probe, before, after, basis):
        changes.append({"file": file, "probe_id": probe, "before": before,
                        "after": after, "basis": basis})

    # ---------------- equiv ledger ----------------
    eq_path = E1 / "equiv_observations.jsonl"
    shutil.copy2(eq_path, OUT / ("equiv_observations.jsonl.bak_" + TS))
    eq_rows = [json.loads(line) for line in open(eq_path, encoding="utf-8")]

    requeue_equiv = {p: rq[p] for p in need if p != "L1_P96__relop_replace__8"}
    out_rows = []
    for r in eq_rows:
        pid = r.get("probe_id")
        if pid == "L1_P37__index_replace__11":
            archived.append(dict(r))
            before = r.get("evidence_grade")
            r["evidence_grade"] = "LIKELY_EQUIVALENT"
            r["validation_status"] = "pass"
            r["wc1_amendment"] = {
                "at": now(), "action": "regrade_direct",
                "voided_witness": "boundary_last_element (kernel "
                                  "nondeterministic at position, H2)",
                "net_stress_pass": 10, "threshold": "stress_pass>=8",
                "basis": "wc1_report regrade_plan + ruling WC1_20260731 #1",
            }
            note_change("equiv_observations.jsonl", pid, before,
                        "LIKELY_EQUIVALENT", "direct regrade (net stress 10>=8)")
        elif pid in requeue_equiv:
            archived.append(dict(r))
            rr = requeue_equiv[pid]
            before = r.get("evidence_grade")
            after = rr["outcome"]
            if after == "INCONCLUSIVE":
                after = "KERNEL_UNDECIDABLE"
            new_row = {
                "probe_id": pid,
                "kernel": rr["kernel"],
                "operator_name": rr["operator_name"],
                "fault_class": rr["fault_class"],
                "validation_status": rr["validation_status"],
                "evidence_grade": after,
                "divergence": rr.get("divergence"),
                "trials": rr.get("trials"),
                "valid_rounds": rr.get("valid_rounds"),
                "wall_ms": rr.get("wall_ms"),
                "timed_out": rr.get("timed_out"),
                "finished_at": rr.get("finished_at"),
                "evidence": rr.get("evidence"),
                "wc1_amendment": {
                    "at": now(), "action": "requeue_replaced",
                    "requeue_run": "requeue_final",
                    "poisoned_excluded": rr.get("poisoned_excluded"),
                    "basis": "wc1_report regrade_plan REQUEUE_THEN_GRADE + "
                             "ruling WC1_20260731",
                },
            }
            r = new_row
            note_change("equiv_observations.jsonl", pid, before, after,
                        "requeue_final outcome")
        elif pid in ("L2_P68__relop_replace__3", "L2_P98__mask_boundary__3"):
            r["wc1_annotation"] = {
                "at": now(), "verdict": "CONFIRMED_INTERMITTENT",
                "note": "witness reproduced in both audit passes but not on "
                        "first replay; control arm 0 flakes; preregistered "
                        "rule >=2 merged reproductions keeps WITNESSED",
                "basis": "ruling WC1_20260731 #3",
            }
            note_change("equiv_observations.jsonl", pid,
                        "WITNESSED_NON_EQUIVALENT",
                        "WITNESSED_NON_EQUIVALENT (annotated intermittent)",
                        "ruling #3 rule")
        out_rows.append(r)
    tmp = eq_path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in out_rows:
            fh.write(json.dumps(r, default=str) + "\n")
    tmp.replace(eq_path)

    # ---------------- cse signoff requeue ledger (P37 sync_remove_1) -------
    p = E1 / "cse_observations_lane3_signoff_requeue.jsonl"
    shutil.copy2(p, OUT / (p.name + ".bak_" + TS))
    rows = [json.loads(line) for line in open(p, encoding="utf-8")]
    for r in rows:
        if r.get("probe_id") == "L1_P37__sync_remove__1":
            archived.append(dict(r))
            before = r.get("outcome")
            r["outcome"] = "STILL_LIKELY_EQUIVALENT"
            r["validation_status"] = "pass"
            r["wc1_amendment"] = {
                "at": now(), "action": "regrade_direct",
                "voided_witness": "sparse_extreme/boundary_last_element "
                                  "(kernel nondeterministic, H2)",
                "net_rounds": {"valid": 99, "random_pass": 40,
                               "stress_pass": 59},
                "threshold": "valid>=77 and random>=30 and stress>=42",
                "basis": "wc1_report regrade_plan + ruling WC1_20260731 #1",
            }
            note_change(p.name, r["probe_id"], before,
                        "STILL_LIKELY_EQUIVALENT", "direct regrade")
    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")
    tmp.replace(p)

    # ---------------- cse lane3 ledger (P96 replace, P94 annotate) ---------
    p = E1 / "cse_observations_lane3.jsonl"
    shutil.copy2(p, OUT / (p.name + ".bak_" + TS))
    rows = [json.loads(line) for line in open(p, encoding="utf-8")]
    for i, r in enumerate(rows):
        pid = r.get("probe_id")
        if pid == "L1_P96__relop_replace__8":
            archived.append(dict(r))
            rr = rq[pid]
            before = r.get("outcome")
            after = rr["outcome"]
            if after == "INCONCLUSIVE":
                after = "KERNEL_UNDECIDABLE"
            rows[i] = {
                "probe_id": pid,
                "kernel": rr["kernel"],
                "operator_name": rr["operator_name"],
                "fault_class": rr["fault_class"],
                "outcome": after,
                "validation_status": rr["validation_status"],
                "divergence": rr.get("divergence"),
                "trials": rr.get("trials"),
                "valid_rounds": rr.get("valid_rounds"),
                "wall_ms": rr.get("wall_ms"),
                "timed_out": rr.get("timed_out"),
                "finished_at": rr.get("finished_at"),
                "evidence": rr.get("evidence"),
                "wc1_amendment": {
                    "at": now(), "action": "requeue_replaced",
                    "requeue_run": "requeue_final",
                    "basis": "wc1_report UNCONFIRMED + ruling WC1_20260731 #2",
                },
            }
            note_change(p.name, pid, before, after, "requeue_final outcome")
        elif pid == "L1_P94__const_perturb__7":
            r["wc1_annotation"] = {
                "at": now(), "verdict": "CONFIRMED_INTERMITTENT",
                "note": "witness reproduced in audit (j=1 second pass); "
                        "control arm 45 clean rounds; FALSIFIED kept per "
                        "preregistered rule",
                "basis": "ruling WC1_20260731 #3",
            }
            note_change(p.name, pid, "FALSIFIED",
                        "FALSIFIED (annotated intermittent)", "ruling #3 rule")
    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")
    tmp.replace(p)

    # ---------------- archives + manifest + final counts -------------------
    with open(OUT / "archived_rows.jsonl", "a", encoding="utf-8") as fh:
        for r in archived:
            fh.write(json.dumps(r, default=str) + "\n")

    # recount final ledger state
    import glob
    from collections import Counter
    eq_cnt = Counter()
    for line in open(eq_path, encoding="utf-8"):
        eq_cnt[json.loads(line).get("evidence_grade")] += 1
    cse_cnt = Counter()
    cse_seen = {}
    for f in sorted(glob.glob(str(E1 / "cse_observations_lane*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            pid = r["probe_id"]
            prev = cse_seen.get(pid)
            if prev is None or str(r.get("finished_at", "")) >= \
                    str(prev.get("finished_at", "")):
                cse_seen[pid] = r
    for r in cse_seen.values():
        cse_cnt[r.get("outcome")] += 1

    manifest = {
        "amendment_id": "wc1_closure_v1",
        "applied_at": now(),
        "basis": ["wc1_report.json generated 2026-08-01T07:33",
                  "advisor ruling WC1_20260731",
                  "requeue_final run (production protocol)"],
        "changes": changes,
        "final_counts": {
            "equiv": dict(eq_cnt),
            "cse_unique_probes": len(cse_seen),
            "cse": dict(cse_cnt),
        },
    }
    (OUT / "amendment_manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False, default=str),
        encoding="utf-8")
    print(json.dumps(manifest["final_counts"], indent=1))
    print("AMENDMENT_APPLIED changes=%d archived=%d" % (len(changes), len(archived)))


if __name__ == "__main__":
    main()
