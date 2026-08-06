"""One-off inspection of pulled E1 data for the offline analysis pipeline."""
import json
from collections import Counter
from pathlib import Path

D = Path("MutakernelV2/实验/重跑实验数据/离线分析/data/e1")


def rows(name):
    with open(D / name, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


eq = list(rows("equiv_observations.jsonl"))
print("equiv rows:", len(eq), "unique probes:", len({r["probe_id"] for r in eq}))
print("grades:", Counter(r.get("evidence_grade") for r in eq))
wit = [r for r in eq if r.get("evidence_grade") == "WITNESSED_NON_EQUIVALENT"]
print("witnessed:", len(wit))
print("witness has divergence:", sum(1 for r in wit if r.get("divergence")))
pol = Counter(
    (r.get("divergence") or {}).get("policy")
    or ((r.get("divergence") or {}).get("round_type") == "random" and "random")
    or "?"
    for r in wit)
print("witness policy:", dict(pol.most_common()))
fails_per_probe = Counter()
for r in wit:
    n = sum(1 for t in (r.get("trials") or []) if str(t.get("status", "")).lower() == "fail")
    fails_per_probe[n] += 1
print("fail-trials per witnessed probe:", dict(fails_per_probe))
n_trials = Counter(len(r.get("trials") or []) for r in eq)
print("trials-count dist (top):", n_trials.most_common(8))
print("wall_ms present:", sum(1 for r in eq if isinstance(r.get("wall_ms"), (int, float))))
sample_stress = next(t for r in eq for t in (r.get("trials") or []) if t.get("round_type") == "stress")
print("sample stress trial keys:", sorted(sample_stress.keys()))
policies = sorted({t.get("policy") for r in eq for t in (r.get("trials") or []) if t.get("policy")})
print("equiv distinct policies:", len(policies), policies)

for lane in [1, 2]:
    cs = list(rows(f"cse_observations_lane{lane}.jsonl"))
    print(f"\ncse lane{lane}:", len(cs), Counter(r.get("outcome") for r in cs))
    print("  unique probes:", len({r['probe_id'] for r in cs}))
    f = [r for r in cs if r.get("outcome") == "FALSIFIED"]
    for r in f:
        print("  FALSIFIED:", r["probe_id"], r.get("witness_policy"), r.get("witness_round"))
    cp = sorted({t.get("policy") for r in cs for t in (r.get("trials") or []) if t.get("policy")})
    print("  distinct policies:", len(cp))
    print("  trials counts:", Counter(len(r.get("trials") or []) for r in cs).most_common(5))

bl = list(rows("baseline_observations.jsonl"))
print("\nbaseline rows:", len(bl), Counter(r.get("status") for r in bl))
print("baseline wall_ms present:", sum(1 for r in bl if isinstance(r.get("wall_ms"), (int, float))))

ctrl = json.loads((D / "original_controls.json").read_text(encoding="utf-8"))
print("controls:", len(ctrl), Counter(v["status"] for v in ctrl.values()))
print("control wall_ms present:", sum(1 for v in ctrl.values() if isinstance(v.get("wall_ms"), (int, float))))

# overlap between equiv witnessed and CSE targets (should be disjoint)
cse_ids = {r["probe_id"] for lane in [1, 2] for r in rows(f"cse_observations_lane{lane}.jsonl")}
print("\nwitnessed ∩ cse:", len({r['probe_id'] for r in wit} & cse_ids))
print("INSPECT_DONE")
