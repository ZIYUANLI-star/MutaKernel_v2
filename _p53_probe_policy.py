import _remote
c = _remote.connect()
print("=== mixed_extremes policy source ===")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -c \"import inspect;from src.stress import policy_bank as pb;print(inspect.getsource(pb.STRESS_POLICIES['mixed_extremes']))\"", timeout=60)
print("=== P53 problem file (get_inputs) ===")
_remote.run(c, "sed -n '1,80p' /root/mk_v2/KernelBench/KernelBench/level1/53_Min_reduction_over_a_dimension.py", timeout=30)
c.close()
