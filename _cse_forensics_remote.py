"""Remote-side: round-level forensics for the 8 new CSE INCONCLUSIVEs.

Per record: trial breakdown by (round_type, status, reason-class), sampled
raw reasons/errors, policy attribution of voided rounds, early-termination
stderr from worker logs, and the equiv-era baseline of the same probe.
"""
import json
import re
from collections import Counter
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")


def rows_of(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def reason_class(text):
    t = (text or "").lower()
    if "nan" in t or "inf" in t:
        return "nan_inf"
    if "resource" in t or "out of memory" in t or "alloc" in t:
        return "resource"
    if "state" in t and "sync" in t or "state_dict" in t:
        return "state_sync"
    if "timed out" in t or "watchdog" in t:
        return "round_timeout"
    if not t.strip():
        return "empty"
    return "other:" + t[:60]


targets = []
for lane in (3, 4, 5):
    for r in rows_of(E1 / f"cse_observations_lane{lane}.jsonl"):
        if r.get("outcome") == "INCONCLUSIVE":
            targets.append((lane, r))

equiv_rows = {r["probe_id"]: r for r in rows_of(E1 / "equiv_observations.jsonl")}

for lane, r in targets:
    trials = r.get("trials") or []
    print(f"\n===== lane{lane} {r['probe_id']} wall={r['wall_ms']/1000:.0f}s "
          f"timed_out={r['timed_out']} valid={r.get('valid_rounds')} "
          f"ntrials={len(trials)} class={r.get('inconclusive_class')} =====")
    combo = Counter()
    void_policies = Counter()
    samples = {}
    for t in trials:
        st = str(t.get("status", "")).lower()
        rc = reason_class(t.get("reason", "")) if st != "pass" else ""
        key = (t.get("round_type"), st, rc)
        combo[key] += 1
        if st != "pass":
            void_policies[t.get("policy") or f"random_{t.get('round_index')}"] += 1
            if rc not in samples:
                errs = t.get("errors") or []
                samples[rc] = {
                    "policy": t.get("policy"), "seed": t.get("seed"),
                    "reason": (t.get("reason") or "")[:200],
                    "err_phases": [e.get("phase") for e in errs][:3],
                    "err_msgs": [str(e.get("message"))[:150] for e in errs][:2],
                }
    for k, v in sorted(combo.items(), key=lambda x: -x[1]):
        print("  ", k, v)
    print("  voided-by-policy:", dict(void_policies.most_common(12)))
    for rc, s in samples.items():
        print(f"  sample[{rc}]:", json.dumps(s, ensure_ascii=False))
    # reason field of the whole record
    print("  record.reason:", (r.get("reason") or "")[:200])
    # equiv-era baseline
    eq = equiv_rows.get(r["probe_id"])
    if eq:
        eq_valid = eq.get("valid_rounds")
        print(f"  equiv baseline: grade={eq['evidence_grade']} "
              f"valid_rounds={eq_valid} wall={eq['wall_ms']/1000:.0f}s")
    # worker log stderr (early-termination evidence)
    wl = E1 / "worker_logs" / f"{r['probe_id']}_cse.log"
    if wl.exists():
        txt = wl.read_text(encoding="utf-8", errors="replace")
        stderr = txt.split("STDERR:", 1)[-1].strip()
        tail = stderr[-500:] if stderr else "(empty stderr)"
        print("  worker stderr tail:", re.sub(r"\s+", " ", tail)[-400:])
    else:
        print("  worker log: none")

print("\nFORENSICS_DONE")
