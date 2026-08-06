# -*- coding: utf-8 -*-
"""Probe 4: (a) can torch.lerp reproduce torch.quantile bit-exactly even for
subnormal data, (b) measured peak RSS / wall of OLD vs NEW error_stats so the
giant subjects can be extrapolated.  Memory capped ~20GB on purpose: the
critical-path CSE worker shares the 120GiB cgroup."""
import _remote as R

LERP = r'''
import math, struct
import torch
torch.set_num_threads(24)
def bits(x): return struct.pack("<d", x).hex()

def q_py(a, q):
    last = a.numel() - 1
    rank = q * last
    below = int(rank); w = rank - below
    above = min(below + 1, last)
    lo = float(a[below]); hi = float(a[above])
    if abs(w) < 0.5:
        return lo + w * (hi - lo)
    return hi - (hi - lo) * (1.0 - w)

def q_torch_lerp(a, q):
    last = a.numel() - 1
    rank = q * last
    below = int(rank); w = rank - below
    above = min(below + 1, last)
    return float(torch.lerp(a[below].reshape(1), a[above].reshape(1),
                            torch.tensor([w], dtype=torch.float64)).item())

def q_torch_lerp_scalar(a, q):
    last = a.numel() - 1
    rank = q * last
    below = int(rank); w = rank - below
    above = min(below + 1, last)
    return float(torch.lerp(a[below], a[above], w).item())

torch.manual_seed(0)
bad_py = bad_lerp = bad_lerps = 0
n_cases = 0
for n in [1, 2, 3, 4, 5, 7, 10, 11, 32, 33, 100, 101, 999, 1000, 1001, 65536,
          1000003, 2**24 - 1, 2**24]:
    for kind in ["uniform", "exp", "dup", "tiny", "subnorm", "huge", "zeros", "mixed"]:
        if kind == "uniform":   t = torch.rand(n, dtype=torch.float64)
        elif kind == "exp":     t = torch.rand(n, dtype=torch.float64).mul_(1e-8)
        elif kind == "dup":     t = torch.randint(0, 3, (n,)).to(torch.float64).mul_(0.5)
        elif kind == "tiny":    t = torch.rand(n, dtype=torch.float64).mul_(5e-314)
        elif kind == "subnorm": t = torch.rand(n, dtype=torch.float64).mul_(1e-320)
        elif kind == "huge":    t = torch.rand(n, dtype=torch.float64).mul_(1e300)
        elif kind == "zeros":   t = torch.zeros(n, dtype=torch.float64)
        else:
            t = torch.rand(n, dtype=torch.float64)
            t[: max(1, n // 2)] = 0.0
        s = t.sort().values
        for q in [0.50, 0.90, 0.95, 0.99]:
            ref = bits(float(torch.quantile(t, q).item()))
            n_cases += 1
            if bits(q_py(s, q)) != ref: bad_py += 1
            if bits(q_torch_lerp(s, q)) != ref: bad_lerp += 1
            if bits(q_torch_lerp_scalar(s, q)) != ref: bad_lerps += 1
print("cases=%d  python-lerp mismatch=%d  torch.lerp(1-elem) mismatch=%d  "
      "torch.lerp(0-dim) mismatch=%d" % (n_cases, bad_py, bad_lerp, bad_lerps))
'''

MEM = r'''
import math, os, resource, sys, time
import torch
import numpy as np
torch.set_num_threads(24)
VARIANT = sys.argv[1]
N = int(sys.argv[2])
QLIMIT = 16_777_216

def error_stats_old(output, reference, tol):
    out64 = output.detach().to("cpu", torch.float64).reshape(-1)
    ref64 = reference.detach().to("cpu", torch.float64).reshape(-1)
    abs_err = (out64 - ref64).abs()
    abs_err = torch.where(torch.isfinite(abs_err), abs_err,
                          torch.full_like(abs_err, math.inf))
    nonzero = ref64 != 0.0
    if bool(nonzero.any()):
        rel = (out64[nonzero] - ref64[nonzero]).abs() / ref64[nonzero].abs()
    else:
        rel = torch.zeros(1, dtype=torch.float64)
    finite_abs = abs_err[torch.isfinite(abs_err)]
    def pct(q):
        if finite_abs.numel() == 0: return 0.0
        try:
            return float(torch.quantile(finite_abs, q).item())
        except RuntimeError as e:
            return float("nan")  # measure memory past the known crash point
    return {"count": int(abs_err.numel()),
            "num_exceeding": int((abs_err > tol).sum().item()),
            "max_abs": float(abs_err.max().item()),
            "mean_abs": float(finite_abs.mean().item()),
            "p50_abs": pct(0.50), "p90_abs": pct(0.90), "p99_abs": pct(0.99),
            "max_rel": float(rel.max().item()),
            "mean_rel": float(rel.mean().item())}

def error_stats_new(output, reference, tol):
    flat = output.detach().to("cpu").reshape(-1)
    ref64 = reference.detach().to("cpu", torch.float64).reshape(-1)
    abs_err = torch.sub(flat, ref64); abs_err.abs_()
    finite = torch.isfinite(abs_err)
    all_finite = bool(finite.all())
    if not all_finite:
        abs_err.masked_fill_(finite.logical_not(), math.inf)
    count = abs_err.numel()
    num_exceeding = int((abs_err > tol).sum().item())
    max_abs = float(abs_err.max().item()) if count else 0.0
    nonzero = ref64 != 0.0
    if bool(nonzero.any()):
        if all_finite and bool(nonzero.all()):
            ref64.abs_()
            torch.div(abs_err, ref64, out=ref64)
            rel = ref64
        else:
            num = torch.sub(flat[nonzero], ref64[nonzero]); num.abs_()
            den = ref64[nonzero].abs_(); num.div_(den); del den
            rel = num
    else:
        rel = torch.zeros(1, dtype=torch.float64)
    max_rel = float(rel.max().item()) if rel.numel() else 0.0
    mean_rel = float(rel.mean().item()) if rel.numel() else 0.0
    del rel, ref64, nonzero
    finite_abs = abs_err if all_finite else abs_err[finite]
    del finite
    n_fin = finite_abs.numel()
    mean_abs = float(finite_abs.mean().item()) if n_fin else math.inf
    if n_fin == 0:
        p50 = p90 = p99 = 0.0
    elif n_fin <= QLIMIT:
        p50, p90, p99 = (float(torch.quantile(finite_abs, q).item())
                         for q in (0.50, 0.90, 0.99))
    else:
        arr = finite_abs.numpy(); last = n_fin - 1
        ks = set()
        for q in (0.50, 0.90, 0.99):
            b = int(q * last); ks.add(b); ks.add(min(b + 1, last))
        arr.partition(sorted(ks))
        out = []
        for q in (0.50, 0.90, 0.99):
            rank = q * last; below = int(rank); w = rank - below
            above = min(below + 1, last)
            lo = float(arr[below]); hi = float(arr[above])
            out.append(lo + w * (hi - lo) if abs(w) < 0.5
                       else hi - (hi - lo) * (1.0 - w))
        p50, p90, p99 = out
    return {"count": count, "num_exceeding": num_exceeding, "max_abs": max_abs,
            "mean_abs": mean_abs, "p50_abs": p50, "p90_abs": p90,
            "p99_abs": p99, "max_rel": max_rel, "mean_rel": mean_rel}

torch.manual_seed(1)
ref = (torch.rand(N, dtype=torch.float32) * 20.0 - 10.0)
out = ref + torch.rand(N, dtype=torch.float32) * 1e-4
base = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0
t0 = time.time()
fn = error_stats_old if VARIANT == "old" else error_stats_new
stats = fn(out, ref, 1e-5)
dt = time.time() - t0
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0
print("VARIANT=%s N=%d inputs_only_peak=%.2fGB total_peak=%.2fGB "
      "stats_delta=%.2fGB bytes_per_elem=%.1f wall=%.1fs"
      % (VARIANT, N, base, peak, peak - base,
         (peak - base) * 1073741824.0 / N, dt))
print("  p50=%.6g p90=%.6g p99=%.6g mean_abs=%.6g max_rel=%.6g"
      % (stats["p50_abs"], stats["p90_abs"], stats["p99_abs"],
         stats["mean_abs"], stats["max_rel"]))
'''

c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/_b9fix_lerp.py", "w") as fh:
    fh.write(LERP)
with sftp.open("/root/_b9fix_mem.py", "w") as fh:
    fh.write(MEM)
sftp.close()

print("### A. lerp fidelity")
R.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -u /root/_b9fix_lerp.py 2>&1",
      timeout=1800)
print("### B. memory / wall (separate processes)")
for variant in ["old", "new"]:
    for n in [16_777_216, 100_000_000, 200_000_000]:
        R.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=24 MKL_NUM_THREADS=24 "
                 "/root/miniconda3/bin/python -u /root/_b9fix_mem.py %s %d 2>&1" % (variant, n),
              timeout=1800)
print("### C. cgroup after")
R.run(c, "cat /sys/fs/cgroup/memory/memory.usage_in_bytes /sys/fs/cgroup/memory/memory.failcnt; "
         "ps -eo pid,rss,args | grep '_mutant_[w]orker' | awk '{print $1,$2}'", timeout=60)
c.close()
print("PROBE4_DONE")
