import _remote
c = _remote.connect()
R = _remote.run
script = r'''
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
'''
open("_wc24_tmp.py","w").write(script)
s = c.open_sftp(); s.put("_wc24_tmp.py", "/root/mk_v2/_wc24_tmp.py"); s.close()
code, out, err = R(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _wc24_tmp.py", timeout=300, echo=False)
open("_wc_ref/p37_kernel.txt", "w", encoding="utf-8").write(out + "\nSTDERR\n" + err)
print(out[:12000])
c.close()
