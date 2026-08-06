import _remote
c = _remote.connect()
print("=== _mixed_extremes + _make_policy source ===")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -c \"import inspect;from src.stress import policy_bank as pb;print(inspect.getsource(pb._mixed_extremes));print('=====MAKE=====');print(inspect.getsource(pb._make_policy))\"", timeout=60)
print("=== control3 log ===")
_remote.run(c, "cat /root/mk_v2_runs/e1/_p53_control3.log", timeout=30)
print("=== control3 procs ===")
_remote.run(c, "ps -eo pid,etime,cmd | grep -E '_inner_one|control3' | grep -v grep", timeout=30)
c.close()
