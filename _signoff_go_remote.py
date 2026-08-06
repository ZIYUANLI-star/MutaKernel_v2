"""Sign-off ledger execution (advisor-approved 2026-07-30 16:15 CST).

Runs ON THE REMOTE host. Idempotent: each step checks its own marker.

STEP A: equiv ledger - L1_P95__relop_replace__5 INCONCLUSIVE -> WITNESSED
        (SPEC_VIOLATION, deterministic crash + clean control).
STEP B: cse_policy_skip.json - register L1_P37 boundary_last_element skip
        (H2 kernel-level numeric sensitivity: unmutated control self-diverges
        2/3 at the same magnitude -> the round has no discriminative power
        for this kernel; applied uniformly to original and mutants).
STEP C: lane3 CSE ledger - archive the 6 FALSIFIED records whose witnesses
        were voided by the sign-off (#7 env watchdog false crash; 5x P37
        no-discriminative-power rounds) and drop the ids from the completed
        checkpoint so the driver re-runs them to a definitive grade.
Launch of the rerun driver is done by the caller (separate nohup command).
"""
import json
import shutil
from datetime import datetime
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")
SIGNED_AT = "2026-07-30T16:15:00+08:00"
NOW = datetime.now().isoformat()

CSE_IDS = {
    "L1_P46__index_replace__5": {
        "decision": "DOWNGRADE_ROUND_ENV_VOID",
        "detail": "candidate_crash witness (mixed_extremes sub1 seed50041) voided as "
                  "90s-watchdog environment artifact; review 3/3 pass at 300s + clean "
                  "control. Remaining evidence (58 pass rounds, stress<42) below the "
                  "preregistered STILL bar -> definitive-grade rerun required.",
        "evidence": "final_window_review/p46_index_replace_5/",
    },
}
P37_DETAIL = ("witness round (boundary_last_element sub0 seed50040) voided: unmutated "
              "control self-diverges 2/3 at the same magnitude (H2 kernel-level numeric "
              "sensitivity), so the round has no discriminative power for L1_P37. "
              "Remaining evidence (73 pass rounds, stress 33<42) below the preregistered "
              "STILL bar -> definitive-grade rerun with the policy skipped.")
for pid in ("L1_P37__arith_replace__14", "L1_P37__sync_remove__1",
            "L1_P37__sync_remove__0", "L1_P37__launch_config_mutate__0",
            "L1_P37__epsilon_modify__0"):
    CSE_IDS[pid] = {"decision": "H2_KERNEL_NUMERIC_SENSITIVITY",
                    "detail": P37_DETAIL,
                    "evidence": "final_window_review/p37_cluster/"}


def backup(path: Path):
    bak = path.with_name(path.name + ".bak_signoff")
    if not bak.exists():
        shutil.copy2(path, bak)
        print(f"  backup {path.name} -> {bak.name}")
    else:
        print(f"  backup exists: {bak.name}")


def atomic_write(path: Path, text: str):
    tmp = path.with_suffix(path.suffix + ".signoff_tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------- STEP A
def step_a_p95():
    print("STEP A: P95 equiv amendment")
    obs = E1 / "equiv_observations.jsonl"
    lines = obs.read_text(encoding="utf-8").splitlines()
    out, done = [], False
    for line in lines:
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("probe_id") == "L1_P95__relop_replace__5":
            if rec.get("evidence_grade") == "WITNESSED_NON_EQUIVALENT":
                print("  already amended (idempotent skip)")
                return
            backup(obs)
            backup(E1 / "equiv_summary.json")
            with open(E1 / "equiv_observations_signoff_archive.jsonl", "a",
                      encoding="utf-8") as fh:
                arch = dict(rec)
                arch["signoff_archived_at"] = NOW
                arch["signoff_reason"] = "amended to WITNESSED_NON_EQUIVALENT (SPEC_VIOLATION)"
                fh.write(json.dumps(arch, ensure_ascii=False) + "\n")
            rec["validation_status"] = "fail"
            rec["evidence_grade"] = "WITNESSED_NON_EQUIVALENT"
            rec["inconclusive_class"] = None
            rec["witness"] = {
                "type": "spec_violation_crash",
                "detail": "deterministic CUDA illegal memory access on candidate "
                          "(reproduced in exclusive-window retry); unmutated control "
                          "clean (LIKELY_EQUIVALENT)",
                "review_evidence": "final_window_review/p95_relop_replace_5/",
            }
            rec["signoff"] = {
                "decision": "SPEC_VIOLATION",
                "original_grade": "INCONCLUSIVE",
                "signed_at": SIGNED_AT,
                "signed_by": "advisor",
                "applied_at": NOW,
            }
            done = True
        out.append(json.dumps(rec, ensure_ascii=False))
    if not done:
        raise SystemExit("P95 record not found!")
    atomic_write(obs, "\n".join(out) + "\n")
    # regenerate summary grades
    from collections import Counter
    grades = Counter()
    inc_classes = Counter()
    n = 0
    for line in obs.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        n += 1
        grades[r.get("evidence_grade")] += 1
        if r.get("evidence_grade") == "INCONCLUSIVE":
            inc_classes[r.get("inconclusive_class")] += 1
    sp = E1 / "equiv_summary.json"
    summ = json.loads(sp.read_text(encoding="utf-8"))
    summ["completed"] = n
    summ["grades"] = dict(grades)
    summ["inconclusive_classes"] = dict(inc_classes)
    summ["signoff_amendment"] = {
        "probe": "L1_P95__relop_replace__5",
        "change": "INCONCLUSIVE -> WITNESSED_NON_EQUIVALENT (SPEC_VIOLATION)",
        "signed_at": SIGNED_AT, "applied_at": NOW,
    }
    atomic_write(sp, json.dumps(summ, indent=2, ensure_ascii=False))
    print(f"  amended; new grades: {dict(grades)} (n={n})")


# ---------------------------------------------------------------- STEP B
def step_b_policy_skip():
    print("STEP B: register L1_P37 boundary_last_element skip")
    p = E1 / "cse_policy_skip.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    if "L1_P37" in raw.get("skip", {}):
        print("  already registered (idempotent skip)")
        return
    backup(p)
    raw["skip"]["L1_P37"] = ["boundary_last_element"]
    raw["p37_reason"] = (
        "Sign-off decision H2_KERNEL_NUMERIC_SENSITIVITY (advisor, "
        f"{SIGNED_AT}): the UNMUTATED L1_P37 kernel itself diverges 2/3 under "
        "boundary_last_element/seed50040 (max_abs_err 0.0437/0.0348, same "
        "magnitude as the mutants), i.e. last-element-extreme x reduction-order "
        "sensitivity of the kernel, not mutant semantics. The policy round "
        "therefore has no discriminative power for this kernel and is skipped "
        "uniformly for the original and every mutant. Evidence: "
        "final_window_review/p37_cluster/. Planned stress rounds shrink; the "
        "absolute pass bar CSE_MIN_STRESS_ROUNDS=42 is unchanged (stricter "
        "pass-rate, never looser).")
    atomic_write(p, json.dumps(raw, indent=2, ensure_ascii=False))
    print("  registered")


# ---------------------------------------------------------------- STEP C
def step_c_requeue():
    print("STEP C: lane3 archive + requeue of 6 sign-off ids")
    op = E1 / "cse_observations_lane3.jsonl"
    cp = E1 / "cse_completed_lane3.json"
    archive = E1 / "cse_observations_signoff_archive.jsonl"
    lines = op.read_text(encoding="utf-8").splitlines()
    keep, move = [], []
    for line in lines:
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("probe_id") in CSE_IDS and rec.get("outcome") == "FALSIFIED":
            move.append(rec)
        else:
            keep.append(line)
    completed = json.loads(cp.read_text(encoding="utf-8"))
    present = [i for i in CSE_IDS if i in completed]
    if not move and not present:
        print("  already requeued (idempotent skip)")
        return
    backup(op)
    backup(cp)
    with open(archive, "a", encoding="utf-8") as fh:
        for rec in move:
            arch = dict(rec)
            info = CSE_IDS[rec["probe_id"]]
            arch["signoff"] = {
                "decision": info["decision"],
                "witness_voided": True,
                "detail": info["detail"],
                "evidence": info["evidence"],
                "signed_at": SIGNED_AT,
                "signed_by": "advisor",
                "applied_at": NOW,
                "action": "archived + requeued for definitive-grade rerun "
                          "(tag signoff_requeue)",
            }
            fh.write(json.dumps(arch, ensure_ascii=False) + "\n")
    atomic_write(op, "\n".join(keep) + ("\n" if keep else ""))
    remaining = [i for i in completed if i not in CSE_IDS]
    atomic_write(cp, json.dumps(sorted(remaining)))
    print(f"  archived {len(move)} obs line(s); lane3 obs {len(lines)} -> {len(keep)}; "
          f"completed {len(completed)} -> {len(remaining)}")
    manifest = {
        "signed_at": SIGNED_AT,
        "signed_by": "advisor",
        "applied_at": NOW,
        "decisions": {
            "p46_#7": "DOWNGRADE_ROUND_ENV_VOID -> rerun (round_timeout raised to 300s)",
            "p37_cluster_5": "H2_KERNEL_NUMERIC_SENSITIVITY -> boundary_last_element "
                             "skipped for L1_P37, rerun",
            "p95_equiv": "SPEC_VIOLATION amendment applied in equiv ledger",
        },
        "requeued_ids": sorted(CSE_IDS),
        "archive_file": archive.name,
        "rerun_tag": "signoff_requeue",
    }
    (E1 / "cse_signoff_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print("  wrote cse_signoff_manifest.json")


if __name__ == "__main__":
    step_a_p95()
    step_b_policy_skip()
    step_c_requeue()
    print("SIGNOFF_LEDGER_DONE")
