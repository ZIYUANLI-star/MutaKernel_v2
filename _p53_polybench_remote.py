#!/usr/bin/env python3
"""Safe reduced-scale benchmark of all 21 stress policies on a P53-shaped input.

Uses 1/16 of the real numel (128 x 256 x 4095 ~= 134M elems, ~0.5GB) so it can
NOT threaten the 120GB cgroup or the running lanes. Times each policy's input
generation on CPU and extrapolates x16 to the real P53 size. Ranks policies to
decide which are budget-hostile for P53's 2.1B-element input.
"""
import sys, time, gc
from pathlib import Path
ROOT = Path("/root/mk_v2"); sys.path.insert(0, str(ROOT))
import torch
from src.stress.policy_bank import STRESS_POLICIES, get_all_policy_names

# real P53: (128, 4096, 4095). Reduce middle dim by 16 -> (128, 256, 4095).
SCALE = 16
small_shape = (128, 4096 // SCALE, 4095)
real_numel = 128 * 4096 * 4095
small_numel = 128 * (4096 // SCALE) * 4095
print(f"small_shape={small_shape} small_numel={small_numel} real_numel={real_numel} scale={SCALE}")

def make_template():
    return [torch.rand(*small_shape, dtype=torch.float32)]

rows = []
for name in get_all_policy_names():
    fn = STRESS_POLICIES[name]
    template = make_template()
    gc.collect()
    t0 = time.time()
    try:
        out = fn(template, 50040)
        dt = time.time() - t0
        del out
        rows.append((name, dt, dt * SCALE, None))
    except Exception as e:
        dt = time.time() - t0
        rows.append((name, dt, dt * SCALE, f"{type(e).__name__}: {str(e)[:80]}"))
    del template
    gc.collect()

rows.sort(key=lambda r: r[2], reverse=True)
print(f"{'policy':22s} {'small_s':>8s} {'extrap_full_s':>14s}  note")
for name, small_s, full_s, note in rows:
    print(f"{name:22s} {small_s:8.2f} {full_s:14.1f}  {note or ''}")
