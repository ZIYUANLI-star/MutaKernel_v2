"""Remote smoke: generate all four baseline plans for one wave-1 subject."""
import _remote

SID = "C3__KB_L1_P1__4a3041f5d0ed8360"
c = _remote.connect()
_, o, e = _remote.run(c, (
    "cd /root/mk_v2 && mkdir -p /root/mk_v2_runs/e3_campaign/smoke && "
    "for B in b1u b7 b8; do "
    "/root/miniconda3/bin/python scripts/run_e3_external.py plan --baseline $B "
    "--subject-id %s --out /root/mk_v2_runs/e3_campaign/smoke/plan_$B.json; done; "
    "/root/miniconda3/bin/python scripts/run_e3_external.py plan --baseline b9 "
    "--subject-id %s --b9-dtypes float32 float16 "
    "--out /root/mk_v2_runs/e3_campaign/smoke/plan_b9.json; "
    "echo ---; ls -la /root/mk_v2_runs/e3_campaign/smoke/" % (SID, SID)),
    timeout=300, echo=False)
print(o)
if e.strip():
    print("STDERR:\n" + e[-1500:])
c.close()
