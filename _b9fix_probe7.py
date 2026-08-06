# -*- coding: utf-8 -*-
"""Probe 7: does the intra-op thread count change the recorded mean_abs /
mean_rel bit patterns?  The first 31 units ran under OMP_NUM_THREADS=24; if the
answer is yes, the resume run must pin the same value or the means stop being
bit-comparable."""
import _remote as R

SNIPPET = r'''
import struct, subprocess, sys
import torch

def bits(x): return struct.pack("<d", x).hex()

if len(sys.argv) > 1:
    threads = int(sys.argv[1])
    torch.set_num_threads(threads)
    torch.manual_seed(7)
    t = torch.rand(50_000_000, dtype=torch.float64) * 1e-4
    print("threads=%d torch.get_num_threads=%d mean=%s sum=%s"
          % (threads, torch.get_num_threads(), bits(float(t.mean().item())),
             bits(float(t.sum().item()))))
    raise SystemExit(0)

print("default torch.get_num_threads =", torch.get_num_threads())
for n in [1, 8, 24, 24, 56, 112]:
    subprocess.run([sys.executable, __file__, str(n)])
'''

c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/_b9fix_threads.py", "w") as fh:
    fh.write(SNIPPET)
sftp.close()
R.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -u /root/_b9fix_threads.py 2>&1",
      timeout=900)
c.close()
print("PROBE7_DONE")
