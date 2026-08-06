"""Interim deep-dive of run5: control outcomes, probe outcomes, paired flips,
and comparison against run4 expectations."""
import json
from collections import Counter, defaultdict

recs = [json.loads(l) for l in open("_run5_observations.jsonl", encoding="utf-8")
        if l.strip()]
controls = json.load(open("_run5_controls.json", encoding="utf-8"))

print(f"### probes completed: {len(recs)}")
print(f"### controls executed: {len(controls)}")

print("\n--- CONTROLS (legacy, corrected) ---")
cc = Counter((v["legacy"]["status"], v["corrected"]["status"]) for v in controls.values())
for k, v in cc.most_common():
    print(f"  {k}: {v}")

print("\n--- controls where corrected is NOT survived ---")
for k, v in controls.items():
    cs = v["corrected"]["status"]
    if cs != "survived":
        print(f"  {k}: legacy={v['legacy']['status']} corrected={cs} "
              f"err={v['corrected'].get('error','')[:120]}")

print("\n--- PROBES by stratum ---")
strata = defaultdict(lambda: Counter())
flips = []
for r in recs:
    s = {True: "stateful", False: "stateless", None: "unknown"}[r.get("reference_stateful")]
    key = f"L{r['level']}-{s}"
    ok = bool(r.get("original_control_ok"))
    strata[key]["total"] += 1
    strata[key]["control_ok"] += ok
    if ok:
        fp = r.get("flip_paired")
        if fp is None:
            strata[key]["inconclusive_pair"] += 1
        else:
            strata[key]["paired_analyzable"] += 1
            if fp:
                strata[key]["paired_flip"] += 1
                flips.append(r)
        fh = r.get("flip_vs_historical")
        if fh is not None:
            strata[key]["hist_n"] += 1
            if fh:
                strata[key]["hist_flip"] += 1
for k in sorted(strata):
    print(f"  {k}: {dict(strata[k])}")

print("\n--- PAIRED FLIPS so far ---")
for r in flips:
    print(f"  {r['probe_id']}: hist={r['historical_status']} "
          f"legacy={r['legacy']['status']} corrected={r['corrected']['status']}")

print("\n--- pair-status matrix (control-ok probes) ---")
pm = Counter((r["legacy"]["status"], r["corrected"]["status"])
             for r in recs if r.get("original_control_ok"))
for k, v in pm.most_common():
    print(f"  legacy={k[0]:<10} corrected={k[1]:<10} n={v}")

print("\n--- non-analyzable probes (control not ok) detail ---")
bad = [r for r in recs if not r.get("original_control_ok")]
bc = Counter()
for r in bad:
    ctrl = controls.get(r["problem_name"], {})
    bc[(ctrl.get("legacy", {}).get("status"), ctrl.get("corrected", {}).get("status"))] += 1
for k, v in bc.most_common():
    print(f"  control(legacy={k[0]}, corrected={k[1]}): {v} probes")

print("\n--- avg minutes per probe (wall) ---")
if len(recs) >= 2:
    from datetime import datetime
    t0 = datetime.fromisoformat(recs[0]["started_at"])
    t1 = datetime.fromisoformat(recs[-1]["finished_at"])
    mins = (t1 - t0).total_seconds() / 60
    print(f"  {len(recs)} probes in {mins:.0f} min -> {mins/len(recs):.1f} min/probe; "
          f"remaining {153 - len(recs)} -> ~{(153 - len(recs)) * mins / len(recs) / 60:.1f} h")
