import _remote

c = _remote.connect()
for lane in (3, 4, 5):
    _remote.run(c, f"grep 'cse-falsify (lane' /root/mk_v2_runs/e1_cse_lane{lane}.log | tail -1", timeout=30)
_remote.run(c, "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; "
               "nvidia-smi --query-gpu=memory.used --format=csv,noheader", timeout=30)
c.close()
print("BANNER_DONE")
