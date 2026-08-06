import _remote
c = _remote.connect()
R = _remote.run
script = r'''
import sys, inspect
sys.path.insert(0, "/root/mk_v2")
from src.stress.policy_bank import STRESS_POLICIES
print("policies:", sorted(STRESS_POLICIES))
import src.stress.policy_bank as pb
print("HIGH_MEM?", [n for n in dir(pb) if "HIGH" in n or "MEM" in n])
src = inspect.getsource(pb)
print("source len", len(src))
for name in ("_head_heavy", "_identity", "_random"):
    if name in src:
        print("has", name)
print(src[:2500])
'''
open("_wc11_tmp.py","w").write(script)
s = c.open_sftp(); s.put("_wc11_tmp.py", "/root/mk_v2/_wc11_tmp.py"); s.close()
R(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _wc11_tmp.py", timeout=300)
print("=== b9 lane0 ===")
R(c, "tail -2 /root/mk_v2_runs/e3_b9_calib/lane_v2_0.log; tail -2 /root/mk_v2_runs/e3_b9_calib/lane_v2_1.log")
c.close()
