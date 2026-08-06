# -*- coding: utf-8 -*-
"""Probe 8: can glibc allocator tuning cut the error_stats host high-water?
The real fp64 buffers account for ~18 B/output element; the measured peak is
34, so ~16 B/elem is allocator retention.  Also confirms the stats are
bit-identical under every setting (they must be: the arithmetic is untouched)."""
import _remote as R

SNIPPET = r'''
import resource, struct, sys, time
import torch
sys.path.insert(0, "/root/mk_v2")
from src.experiments.external_ports.b9_seeded_fuzzing import error_stats
torch.set_num_threads(24)
N = 200_000_000
torch.manual_seed(1)
ref = torch.rand(N, dtype=torch.float32) * 20.0 - 10.0
out = ref + torch.rand(N, dtype=torch.float32) * 1e-4
base = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0
t0 = time.time()
s = error_stats(out, ref, 1e-5)
dt = time.time() - t0
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0
print("base=%.2fGB peak=%.2fGB delta=%.2fGB bytes/elem=%.1f wall=%.1fs"
      % (base, peak, peak - base, (peak - base) * 1073741824.0 / N, dt))
print("fingerprint p50=%s p90=%s p99=%s mean_abs=%s mean_rel=%s"
      % tuple(struct.pack("<d", s[k]).hex() for k in
              ("p50_abs", "p90_abs", "p99_abs", "mean_abs", "mean_rel")))
'''

c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/_b9fix_malloc.py", "w") as fh:
    fh.write(SNIPPET)
sftp.close()
for label, env in [
    ("baseline", ""),
    ("arena_max=2", "MALLOC_ARENA_MAX=2 "),
    ("arena_max=1 trim=0", "MALLOC_ARENA_MAX=1 MALLOC_TRIM_THRESHOLD_=0 MALLOC_MMAP_THRESHOLD_=131072 "),
]:
    print("### " + label)
    R.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=24 MKL_NUM_THREADS=24 "
             "%s/root/miniconda3/bin/python -u /root/_b9fix_malloc.py 2>&1" % env,
          timeout=900)
c.close()
print("PROBE8_DONE")
