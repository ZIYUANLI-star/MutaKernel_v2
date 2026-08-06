
import sys, json
sys.path.insert(0, "/root/mk_v2")
from pathlib import Path
import scripts.run_e1_probe_study as ps
E1 = Path("/root/mk_v2_runs/e1")
pfs = ps._load_probe_files(E1)
for kf in pfs:
    kk = kf["kernel"]
    if "L%s_P%s" % (kk["level"], kk["problem_id"]) == "L1_P37":
        print("kernel meta:", json.dumps({k: v for k, v in kk.items()
              if k not in ("source",)})[:600])
        src = kf["kernel_source"]
        print("SOURCE LEN", len(src))
        print("=" * 70)
        print(src)
        print("=" * 70)
        print("probes on L1_P37:", [p["probe_id"] for p in kf["probes"]])
        pf = ps._resolve_problem_file(Path("/root/mk_v2/KernelBench"),
                                      kk["level"], kk["problem_id"])
        print("problem file:", pf)
        print(open(pf).read())
        break
