
import json, collections, sys, os
sys.path.insert(0, "/root/mk_v2")
E1 = "/root/mk_v2_runs/e1"
inv = json.load(open(E1 + "/_wc_witness_inventory.json"))
kernels = sorted({r["kernel"] for r in inv})

# --- per-round cost from production equiv records ---
eq = [json.loads(l) for l in open(E1 + "/equiv_observations.jsonl") if l.strip()]
cost = collections.defaultdict(list)
for r in eq:
    k = r.get("kernel")
    tr = r.get("trials") or []
    rand = [t for t in tr if t.get("round_type") == "random"]
    stress = [t for t in tr if t.get("round_type") == "stress"]
    def tot(ts):
        return sum((t.get("timings_ms") or {}).get("total_ms", 0.0) for t in ts)
    if rand:
        cost[k].append(("rand", tot(rand) / len(rand)))
    if stress:
        cost[k].append(("stress", tot(stress) / len(stress)))

print("=== per-round ms (median over probes) for witness kernels ===")
per = {}
for k in kernels:
    rs = sorted(v for t, v in cost[k] if t == "rand")
    ss = sorted(v for t, v in cost[k] if t == "stress")
    mr = rs[len(rs)//2] if rs else None
    ms = ss[len(ss)//2] if ss else None
    per[k] = (mr, ms)
    print(f"  {k:8s} rand={mr if mr is None else round(mr)}ms  stress={ms if ms is None else round(ms)}ms")
json.dump(per, open(E1 + "/_wc_round_cost.json", "w"), indent=1)

# --- construction seed sensitivity: get_init_inputs + param count ---
import scripts.run_e1_probe_study as ps
from pathlib import Path
probe_files = ps._load_probe_files(Path(E1))
kf_by_kernel = {}
for kf in probe_files:
    kk = kf["kernel"]
    kid = "L%s_P%s" % (kk["level"], kk["problem_id"])
    kf_by_kernel[kid] = kf
print("\n=== probe file kernel ids sample ===", list(kf_by_kernel)[:5])
print("witness kernels found in probe files:",
      sum(1 for k in kernels if k in kf_by_kernel), "/", len(kernels))
missing = [k for k in kernels if k not in kf_by_kernel]
print("missing:", missing)

print("\n=== get_init_inputs / construction seed sensitivity ===")
import importlib.util
sens = {}
for k in kernels:
    kf = kf_by_kernel.get(k)
    if kf is None:
        continue
    pf = ps._resolve_problem_file(Path("/root/mk_v2/KernelBench"),
                                  kf["kernel"]["level"], kf["kernel"]["problem_id"])
    src = open(pf).read()
    has_init = "def get_init_inputs" in src
    body = src.split("def get_init_inputs", 1)[1][:400] if has_init else ""
    ctor_rng = any(t in src for t in ("nn.Parameter", "nn.Conv", "nn.Linear",
                                      "nn.BatchNorm", "nn.Embedding", "torch.randn(",
                                      "torch.rand("))
    sens[k] = {"problem_file": str(pf), "get_init_inputs_body": " ".join(body.split())[:200],
               "ctor_rng_hint": ctor_rng}
    print(f"  {k:8s} init={' '.join(body.split())[:90]!r}")
json.dump(sens, open(E1 + "/_wc_kernel_ctor.json", "w"), indent=1)
print("COST_DONE")
