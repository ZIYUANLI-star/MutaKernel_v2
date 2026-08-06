"""Deploy + run blueprint batch-1 compute, and fetch final offline details."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_bp_batch1_compute_src.py", "/root/mk_v2/_bp_batch1_compute.py")
sftp.close()

_, o, e = _remote.run(
    c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _bp_batch1_compute.py",
    timeout=300, echo=False)
print("=== BP_BATCH1 ===")
print(o)
if e.strip():
    print("STDERR:\n" + e[-2000:])

print("=== A3 BUDGET RECALL CURVE ===")
_, o, _ = _remote.run(c, "cat /root/mk_v2_runs/e1/analysis/final/a3_budget_recall_curve.csv",
                      timeout=30, echo=False)
print(o)

print("=== A4 COST ===")
_, o, _ = _remote.run(c, "cat /root/mk_v2_runs/e1/analysis/final/a4_cost_c1.csv; echo; "
                         "cat /root/mk_v2_runs/e1/analysis/final/a4_cost_c1.json",
                      timeout=30, echo=False)
print(o)

print("=== A3 POLICY YIELD ===")
_, o, _ = _remote.run(c, "cat /root/mk_v2_runs/e1/analysis/final/a3_policy_yield.csv",
                      timeout=30, echo=False)
print(o)
c.close()
