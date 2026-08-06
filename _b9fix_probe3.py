# -*- coding: utf-8 -*-
"""Probe 3 (CPU-only, small tensors): discover torch.quantile's exact numel
limit and verify every candidate rewrite step is BITWISE identical to the
current implementation."""
import _remote as R

SNIPPET = r'''
import math, struct, sys
import torch
import numpy as np
torch.set_num_threads(24)
print("torch", torch.__version__, "numpy", np.__version__)

def bits(x):
    return struct.pack("<d", x).hex()

# ---------------------------------------------------------------- 1. the limit
print()
print("=== 1. torch.quantile numel limit (binary search) ===")
def works(n):
    t = torch.zeros(n, dtype=torch.float64)
    try:
        torch.quantile(t, 0.5)
        return True
    except RuntimeError as e:
        if "too large" in str(e):
            return False
        raise
for n in [2**24 - 1, 2**24, 2**24 + 1, 2**25]:
    print("  n=%d (%s) -> %s" % (n, hex(n), works(n)))
lo, hi = 2**20, 2**25
assert works(lo) and not works(hi)
while lo + 1 < hi:
    mid = (lo + hi) // 2
    if works(mid):
        lo = mid
    else:
        hi = mid
print("  MAX ACCEPTED numel =", lo, "=", hex(lo), "== 2**24 ?", lo == 2**24)
print("  first REJECTED numel =", hi)

# ------------------------------------------------- 2. exact quantile from sort
print()
print("=== 2. sorted-index + lerp reproduction of torch.quantile ===")
def _lerp(low, high, weight):
    if abs(weight) < 0.5:
        return low + weight * (high - low)
    return high - (high - low) * (1.0 - weight)

def q_from_sorted(a_sorted, q):
    last = len(a_sorted) - 1
    rank = q * last
    below = int(rank)
    weight = rank - below
    above = min(below + 1, last)
    return _lerp(float(a_sorted[below]), float(a_sorted[above]), weight)

def q_naive(a_sorted, q):  # the currently-drafted formula (a*(1-w)+b*w)
    last = len(a_sorted) - 1
    pos = q * last
    lo = int(pos)
    hi = min(lo + 1, last)
    frac = pos - lo
    return float(a_sorted[lo] * (1.0 - frac) + a_sorted[hi] * frac)

torch.manual_seed(0)
mismatch_lerp = mismatch_naive = 0
cases = 0
for n in [1, 2, 3, 4, 5, 7, 10, 11, 32, 33, 100, 101, 999, 1000, 1001,
          65536, 1000003, 2**24]:
    for kind in ["uniform", "exp", "dup", "tiny", "huge", "zeros"]:
        if kind == "uniform":
            t = torch.rand(n, dtype=torch.float64)
        elif kind == "exp":
            t = torch.rand(n, dtype=torch.float64).mul_(1e-8)
        elif kind == "dup":
            t = torch.randint(0, 3, (n,)).to(torch.float64).mul_(0.5)
        elif kind == "tiny":
            t = torch.rand(n, dtype=torch.float64).mul_(5e-324 * 1e10)
        elif kind == "huge":
            t = torch.rand(n, dtype=torch.float64).mul_(1e300)
        else:
            t = torch.zeros(n, dtype=torch.float64)
        s = t.sort().values
        arr = s.numpy()
        for q in [0.50, 0.90, 0.99, 0.95]:
            ref = float(torch.quantile(t, q).item())
            a = q_from_sorted(arr, q)
            b = q_naive(arr, q)
            cases += 1
            if bits(a) != bits(ref):
                mismatch_lerp += 1
                if mismatch_lerp <= 5:
                    print("  LERP MISMATCH n=%d %s q=%g: %s vs %s" % (n, kind, q, bits(a), bits(ref)))
            if bits(b) != bits(ref):
                mismatch_naive += 1
                if mismatch_naive <= 5:
                    print("  NAIVE MISMATCH n=%d %s q=%g: %.20g vs %.20g (%s vs %s)"
                          % (n, kind, q, b, ref, bits(b), bits(ref)))
print("  cases=%d  lerp-formula mismatches=%d  naive-formula mismatches=%d"
      % (cases, mismatch_lerp, mismatch_naive))

# --------------------------------------------- 3. numpy in-place partition
print()
print("=== 3. numpy in-place multi-kth partition == full sort order stats ===")
bad = 0
for n in [5, 33, 1001, 1000003]:
    for kind in ["uniform", "dup"]:
        t = (torch.rand(n, dtype=torch.float64) if kind == "uniform"
             else torch.randint(0, 4, (n,)).to(torch.float64))
        truth = t.sort().values.numpy().copy()
        a = t.clone().numpy()          # zero-copy view of the clone
        ks = sorted({int(q * (n - 1)) for q in (0.5, 0.9, 0.99)}
                    | {min(int(q * (n - 1)) + 1, n - 1) for q in (0.5, 0.9, 0.99)})
        a.partition(ks)
        for k in ks:
            if bits(float(a[k])) != bits(float(truth[k])):
                bad += 1
print("  order-stat mismatches after in-place partition:", bad)
t = torch.rand(100, dtype=torch.float64)
v = t.numpy(); v[0] = 12345.0
print("  .numpy() is zero-copy (mutation visible):", float(t[0]) == 12345.0)

# ---------------------------- 4/5/6. bitwise equality of the rewrite steps
print()
print("=== 4. full error_stats: OLD vs NEW, bitwise on every field ===")
QLIMIT = lo   # measured torch limit

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
        if finite_abs.numel() == 0:
            return 0.0
        return float(torch.quantile(finite_abs, q).item())
    return {
        "count": int(abs_err.numel()),
        "num_exceeding": int((abs_err > tol).sum().item()),
        "max_abs": float(abs_err.max().item()) if abs_err.numel() else 0.0,
        "mean_abs": float(finite_abs.mean().item()) if finite_abs.numel() else math.inf,
        "p50_abs": pct(0.50), "p90_abs": pct(0.90), "p99_abs": pct(0.99),
        "max_rel": float(rel.max().item()) if rel.numel() else 0.0,
        "mean_rel": float(rel.mean().item()) if rel.numel() else 0.0,
    }

def error_stats_new(output, reference, tol):
    flat_out = output.detach().to("cpu").reshape(-1)
    ref64 = reference.detach().to("cpu", torch.float64).reshape(-1)
    abs_err = torch.sub(flat_out, ref64)
    abs_err.abs_()
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
            rel = abs_err / ref64.abs()
        else:
            num = torch.sub(flat_out[nonzero], ref64[nonzero])
            num.abs_()
            den = ref64[nonzero].abs_()
            num.div_(den)
            del den
            rel = num
    else:
        rel = torch.zeros(1, dtype=torch.float64)
    max_rel = float(rel.max().item()) if rel.numel() else 0.0
    mean_rel = float(rel.mean().item()) if rel.numel() else 0.0
    del rel, ref64
    finite_abs = abs_err if all_finite else abs_err[finite]
    del finite
    n_fin = finite_abs.numel()
    mean_abs = float(finite_abs.mean().item()) if n_fin else math.inf
    if n_fin == 0:
        p50 = p90 = p99 = 0.0
    elif n_fin <= QLIMIT:
        p50 = float(torch.quantile(finite_abs, 0.50).item())
        p90 = float(torch.quantile(finite_abs, 0.90).item())
        p99 = float(torch.quantile(finite_abs, 0.99).item())
    else:
        arr = finite_abs.numpy()
        last = n_fin - 1
        ks = set()
        for q in (0.50, 0.90, 0.99):
            b = int(q * last)
            ks.add(b); ks.add(min(b + 1, last))
        arr.partition(sorted(ks))
        p50, p90, p99 = (q_from_sorted(arr, q) for q in (0.50, 0.90, 0.99))
    return {
        "count": count, "num_exceeding": num_exceeding, "max_abs": max_abs,
        "mean_abs": mean_abs, "p50_abs": p50, "p90_abs": p90, "p99_abs": p99,
        "max_rel": max_rel, "mean_rel": mean_rel,
    }

def make_case(kind, n, dtype):
    g = torch.Generator().manual_seed(hash((kind, n, str(dtype))) & 0xFFFF)
    ref = (torch.rand(n, generator=g, dtype=torch.float32) * 20 - 10).to(dtype)
    out = ref.clone()
    if kind == "exact":
        pass
    elif kind == "noisy":
        out = (ref.to(torch.float32) + torch.randn(n, generator=g) * 1e-3).to(dtype)
    elif kind == "with_zeros":
        ref = ref.clone(); ref[::7] = 0.0
        out = (ref.to(torch.float32) + torch.randn(n, generator=g) * 1e-3).to(dtype)
    elif kind == "nan":
        out = out.clone(); out[::11] = float("nan")
    elif kind == "inf":
        out = out.clone(); out[::13] = float("inf")
    elif kind == "all_nan":
        out = torch.full_like(out, float("nan"))
    elif kind == "all_inf":
        out = torch.full_like(out, float("inf"))
    elif kind == "all_zero_ref":
        ref = torch.zeros_like(ref); out = torch.zeros_like(out)
    elif kind == "big_err":
        out = (ref.to(torch.float32) * 3.0).to(dtype)
    return out, ref

fails = 0
checked = 0
for dtype in [torch.float32, torch.float16]:
    for n in [1, 2, 3, 17, 1000, 100003]:
        for kind in ["exact", "noisy", "with_zeros", "nan", "inf", "all_nan",
                     "all_inf", "all_zero_ref", "big_err"]:
            out, ref = make_case(kind, n, dtype)
            for tol in [0.0, 1e-5, 1e-2, 1.0]:
                a = error_stats_old(out, ref, tol)
                b = error_stats_new(out, ref, tol)
                checked += 1
                for k in a:
                    va, vb = a[k], b[k]
                    same = (bits(va) == bits(vb) if isinstance(va, float)
                            else va == vb)
                    if isinstance(va, float) and math.isnan(va) and math.isnan(vb):
                        same = True
                    if not same:
                        fails += 1
                        if fails <= 12:
                            print("  MISMATCH dtype=%s n=%d kind=%s tol=%g field=%s: %r vs %r"
                                  % (dtype, n, kind, tol, k, va, vb))
print("  compared %d stat dicts (9 fields each); field mismatches = %d" % (checked, fails))

# empty tensor
print("  empty:", error_stats_old(torch.zeros(0), torch.zeros(0), 1e-5) ==
      error_stats_new(torch.zeros(0), torch.zeros(0), 1e-5))

# --------------------------------- 5. above-limit path vs torch on a tensor
print()
print("=== 5. new path (numpy partition) vs torch.quantile just below limit ===")
n = QLIMIT
t = torch.rand(n, dtype=torch.float64)
ref_q = [float(torch.quantile(t, q).item()) for q in (0.5, 0.9, 0.99)]
arr = t.clone().numpy()
last = n - 1
ks = set()
for q in (0.5, 0.9, 0.99):
    b = int(q * last); ks.add(b); ks.add(min(b + 1, last))
arr.partition(sorted(ks))
new_q = [q_from_sorted(arr, q) for q in (0.5, 0.9, 0.99)]
print("  bitwise equal at n=%d:" % n, all(bits(x) == bits(y) for x, y in zip(ref_q, new_q)))
print("  values", ref_q)

# --------------------------------- 6. div(a,b,out=b) aliasing sanity
print()
print("=== 6. torch.div(a, b, out=b) aliasing ===")
a = torch.rand(1000, dtype=torch.float64) + 1
b = torch.rand(1000, dtype=torch.float64) + 1
want = a / b
try:
    torch.div(a, b, out=b)
    print("  works, bitwise equal:", bool(torch.equal(b, want)))
except Exception as e:
    print("  FAILED:", type(e).__name__, e)

# --------------------------------- 7. isnan/isinf on low dtype == on fp64
print()
print("=== 7. nan/inf detection on original dtype == on fp64 copy ===")
bad = 0
for dtype in [torch.float32, torch.float16]:
    for kind in ["exact", "nan", "inf", "all_nan", "all_inf"]:
        out, ref = make_case(kind, 1000, dtype)
        o64 = out.to(torch.float64)
        if bool(torch.isnan(o64).any()) != bool(torch.isnan(out).any()):
            bad += 1
        if bool(torch.isinf(o64).any()) != bool(torch.isinf(out).any()):
            bad += 1
print("  mismatches:", bad)
print("PROBE3_OK")
'''

c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/_b9fix_probe3.py", "w") as fh:
    fh.write(SNIPPET)
sftp.close()
R.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -u /root/_b9fix_probe3.py 2>&1",
      timeout=1800)
c.close()
print("PROBE3_DONE")
