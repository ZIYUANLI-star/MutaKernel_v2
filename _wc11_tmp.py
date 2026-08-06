
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
