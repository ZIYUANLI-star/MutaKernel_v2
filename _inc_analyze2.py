"""Local analysis pass 2: per-record details for CSE archives (attribution,
rescue candidate, 3600s sufficiency projection), equiv archive closure check,
and the running guard script."""
import json
from collections import Counter

rep = json.load(open("_inc_inventory_report.json", encoding="utf-8"))
rc = rep["reconcile"]

arch = {name: {e["probe_id"]: e for e in entries}
        for name, entries in rc["archived_probe_status"].items()}

print("== CSE archived records, per probe ==")
for r in rep["inconclusive"]:
    if r["phase"] != "cse":
        continue
    ts = r["trial_summary"]
    st = arch.get(r["file"], {}).get(r["probe_id"], {})
    dry = r.get("regrade_dryrun", {})
    done = st.get("in_done_union")
    lane = st.get("lane")
    # projection: rounds completed within the old budget; wall_ms tells budget
    print(f"{r['file'][-20:]:>20} {r['probe_id']:<38} cls={r['inconclusive_class']:<14}"
          f" wall={int((r['wall_ms'] or 0)/1000):>5}s rounds={ts['n_trials']:>3}"
          f" rp={ts['random_pass']:>2} sp={ts['stress_pass']:>2}"
          f" nonpass={ts['non_pass']}(env {ts['env_void_of_non_pass']})"
          f" div={ts['divergence']} dry={dry.get('outcome','?')[:11]:<11}"
          f" done={done} lane={lane}")
    if ts["non_pass_reasons_sample"]:
        for s in ts["non_pass_reasons_sample"][:2]:
            print(f"     reason: {s[:130]}")

print("\n== the rescued env_v1 probe ==")
for r in rep["inconclusive"]:
    if (r["file"] == "cse_observations_env_v1.jsonl"
            and r.get("regrade_dryrun", {}).get("outcome")
            == "STILL_LIKELY_EQUIVALENT"):
        print(json.dumps(r, indent=1)[:2500])

print("\n== equiv archives closure (do archived probes now have a final "
      "non-INC record in merged equiv_observations.jsonl?) ==")
# merged INC record(s)
merged_inc = [r for r in rep["inconclusive"]
              if r["file"] == "equiv_observations.jsonl"]
for r in merged_inc:
    print("merged INC:", r["probe_id"], r["inconclusive_class"],
          "wall_s:", int((r["wall_ms"] or 0)/1000))
    print("  reasons:", r["trial_summary"]["non_pass_reasons_sample"])
arch_equiv = {r["probe_id"] for r in rep["inconclusive"]
              if r["file"].startswith("equiv_observations_timeout")}
print("archived equiv INC unique probes:", len(arch_equiv))

print("\n== guard scripts ==")
print("--- e1_guard.sh (snapshot in report) ---")
print(rep["guard"]["script"] or "(missing)")
