# -*- coding: utf-8 -*-
"""Inspect C2 python_only candidates: what do they actually contain?"""
import json
import re
from collections import Counter

PATH = r"external\C2_cuda_l1\optimized_cuda_code\a100.json"

TRITON = re.compile(r"@triton\.jit|import\s+triton|triton\.language")
CUDA = re.compile(r"__global__|__device__\s|load_inline|cpp_extension|cuda_sources|CUDAExtension|cudaMemcpy|<<<")

markers = Counter()
samples = []
with open(PATH, encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        src = rec.get("custom_code") or ""
        if not src.strip():
            continue
        if TRITON.search(src) or CUDA.search(src):
            continue
        # python_only: what torch/cuda-ish features appear?
        feats = []
        for pat in ["torch.compile", "cuda_graph", "torch.jit", "stream", "channels_last",
                    "torch.backends", "autocast", "half()", "bfloat16", "cudnn",
                    "@torch.jit.script", "CUDAGraph", "load(", "pybind"]:
            if pat in src:
                feats.append(pat)
        markers[tuple(sorted(feats))] += 1
        if len(samples) < 4:
            samples.append((rec["level_id"], rec["task_id"], feats, src[:600]))

print("python_only feature combos:")
for combo, n in markers.most_common(15):
    print(f"  {n:4d}  {combo}")
for lvl, task, feats, head in samples:
    print("=" * 60)
    print(f"L{lvl} T{task} feats={feats}")
    print(head)
