
import sys, inspect, re
sys.path.insert(0, "/root/mk_v2")
import scripts.run_e1_probe_study as ps
print("BASELINE_PROTOCOL:", ps.BASELINE_PROTOCOL)
print("WORKER_CORRECTED:", ps.WORKER_CORRECTED)
print("has run_worker:", hasattr(ps, "run_worker"))
print(inspect.signature(ps.run_worker))
names = [n for n in dir(ps) if n.isupper()]
print("ps constants:", names)
for n in names:
    v = getattr(ps, n)
    if not callable(v):
        print("  ", n, "=", str(v)[:200])

mod = __import__("scripts." + "run_e1_" + "cse_" + "falsify", fromlist=["x"])
print("\n--- falsify constants ---")
for n in dir(mod):
    if n.isupper():
        v = getattr(mod, n)
        if not callable(v):
            print("  ", n, "=", str(v)[:200])

# equiv driver
import glob, os
for p in glob.glob("/root/mk_v2/scripts/run_e1_*equiv*.py") + glob.glob("/root/mk_v2/scripts/*equiv*.py"):
    print("equiv driver file:", p)
print([os.path.basename(p) for p in glob.glob("/root/mk_v2/scripts/run_e1_*.py")])
