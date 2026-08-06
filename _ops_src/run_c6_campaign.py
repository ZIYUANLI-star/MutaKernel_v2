#!/usr/bin/env python3
"""C6 (gpuemu seeded-bug corpus) full-validator campaign — Table 9 (RQ3).

Third-party truth protocol: 26 ops (16 correct controls + 10 seeded bugs),
per-op fp64 reference scripts and per-dtype tolerances shipped BY the corpus
(meta.json).  Every validator row is judged against that fixed protocol; we
never tune tolerances per row.

Validator rows and their preregistered C6 adaptations
-----------------------------------------------------
The corpus interface is a pure forward kernel ``run({name: ndarray}) ->
ndarray``; there is no module state, no autograd path and no layout
sensitivity (kernels flatten/contiguize internally).  Hence:

* ``train`` cases are inapplicable -> replaced by extra value-policy seeds
  (rule: first retained cases, seed+1000000), preserving the 32-call budget;
* ``layout`` cases likewise;
* ``config`` (batch) cases ARE applicable through the op schema's dim
  candidates (parameter ``shape_variant``);
* ``repeated`` cases run the kernel twice on identical inputs and FAIL on
  bitwise self-divergence (nondeterminism surface) in addition to the
  reference check.

Rows: b1-flat-legacy (5 IID, flat 1e-2), b1u (5 IID, corpus tolerances),
b3-iid32, b4-value, b5-boundary, b6-context (dtype x shape grid), m-full,
m-dir (frozen map + kernel-source fingerprint, 70/30), b7-port, b8-port,
b9-port (corpus tolerances = its native calibration), b11 (sanitizer,
alarm types reported separately).

Isolation: one subprocess per (op, row); an async CUDA crash poisons at most
one row of one op.  Resume: per-(op,row) result file.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

MK = Path("/root/mk_v2")
sys.path.insert(0, str(MK))
PYBIN = "/root/miniconda3/bin/python"

VALUE_POLICIES_21 = [
    "large_magnitude", "near_overflow", "near_zero", "denormals",
    "all_negative", "all_positive", "mixed_extremes", "alternating_sign",
    "sparse", "uniform_constant", "structured_ramp", "boundary_last_element",
    "head_heavy", "tail_heavy", "relop_boundary_hit", "extreme_magnitude",
    "near_epsilon", "reduction_adversarial", "init_sensitive",
    "dense_nonzero", "sparse_extreme",
]
B4_POLICIES = ["large_magnitude", "near_zero", "all_negative", "all_positive",
               "sparse", "uniform_constant", "structured_ramp", "mixed_extremes"]
B5_POLICIES = ["boundary_last_element", "relop_boundary_hit", "near_epsilon",
               "near_overflow", "denormals", "reduction_adversarial",
               "head_heavy", "tail_heavy"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# case-stream construction (pure, deterministic)
# ---------------------------------------------------------------------------

def _case(policy, seed, *, dtype=None, shape_variant=0, repeated=False):
    parameters = {"shape_variant": shape_variant}
    if dtype:
        parameters["dtype"] = dtype
    if repeated:
        parameters["repeated"] = True
    return {"policy": policy, "seed": seed, "parameters": parameters,
            "cost": 2 if repeated else 1}


def build_row_cases(row: str, meta: dict, kernel_source: str, op_name: str):
    dtypes = meta.get("dtypes") or ["float32"]
    primary = dtypes[0]
    others = [d for d in dtypes[1:]]

    if row == "b1-flat-legacy":
        return [_case("iid", s) for s in range(5)]
    if row == "b1u":
        return [_case("iid", s) for s in range(5)]
    if row == "b3-iid32":
        return [_case("iid", 1000 + s) for s in range(32)]
    if row == "b4-value":
        return [_case(p, s) for p in B4_POLICIES for s in range(4)]
    if row == "b5-boundary":
        return [_case(p, s) for p in B5_POLICIES for s in range(4)]
    if row == "b6-context":
        cases = []
        seed = 0
        while len(cases) < 32:
            for dtype in dtypes:
                for variant in range(4):
                    cases.append(_case("iid", seed, dtype=dtype,
                                       shape_variant=variant))
                    if len(cases) >= 32:
                        break
                if len(cases) >= 32:
                    break
            seed += 1
        return cases
    if row == "m-full":
        cases = [_case(p, 0) for p in VALUE_POLICIES_21]
        for d in (others or [primary])[:1]:
            cases.append(_case("iid", 0, dtype=d))
        cases.append(_case("iid", 1, dtype=(others or [primary])[0]))
        for variant in range(4):
            cases.append(_case("iid", 0, shape_variant=variant + 1))
        cases.append(_case("iid", 0, repeated=True))  # cost 2
        # train(2) + layout(1) inapplicable -> 3 replacement value seeds
        for i, p in enumerate(VALUE_POLICIES_21[:3]):
            cases.append(_case(p, 1000000 + i))
        total = sum(c["cost"] for c in cases)
        assert total == 32, f"m-full C6 budget {total} != 32"
        return cases
    if row == "m-dir":
        from src.mutengine.fingerprint import build_site_fingerprint
        from src.validator.site_directed import (
            DEFAULT_GENERAL_SEQUENCE, derive_seed, derive_site_directed_plan)
        fault_map = json.loads(
            Path("/root/mk_v2_runs/e1/fault_to_stress_map.json").read_text())
        fp = build_site_fingerprint(kernel_source, op_name)
        derived = derive_site_directed_plan(
            subject_id=f"C6__{op_name}", fingerprint=fp,
            fault_to_stress_map=fault_map, budget_candidate_calls=32,
            directed_fraction=0.7)
        cases = []
        for c in derived["plan"]:
            if c["mode"] == "train":
                continue  # inapplicable (replaced below)
            params = dict(c["parameters"])
            repeated = c["mode"] == "repeated"
            cases.append(_case(c["policy"], c["seed"],
                               dtype=params.get("dtype"),
                               shape_variant=1 if c["mode"] == "config" else 0,
                               repeated=repeated))
        spent = sum(c["cost"] for c in cases)
        rep_round = 1
        while spent < 32:
            progressed = False
            for template in DEFAULT_GENERAL_SEQUENCE:
                if template["mode"] == "train":
                    continue
                cost = 2 if template["mode"] == "repeated" else 1
                if spent + cost > 32:
                    continue
                params = template.get("parameters") or {}
                cases.append(_case(
                    template["policy"],
                    derive_seed(f"C6__{op_name}", template, rep_round),
                    dtype=params.get("dtype"),
                    shape_variant=1 if template["mode"] == "config" else 0,
                    repeated=template["mode"] == "repeated"))
                spent += cost
                progressed = True
                if spent >= 32:
                    break
            if not progressed:
                cases.append(_case("iid", 7000000 + rep_round))
                spent += 1
            rep_round += 1
        return cases
    if row == "b7-port":
        # robust-kbench port: multi-input families x fwd (no params -> no
        # multi-init; backward unsupported by corpus interface)
        cases = []
        for family in ("iid", "large_magnitude", "near_zero", "all_negative"):
            for s in range(8):
                cases.append(_case(family, 2000 + s))
        return cases
    if row == "b8-port":
        # KernelBenchX port: standard + outlier value families
        cases = []
        for family in ("iid", "extreme_magnitude"):
            for s in range(16):
                cases.append(_case(family, 3000 + s))
        return cases
    if row == "b9-port":
        cases = []
        seed = 0
        while len(cases) < 32:
            for dtype in dtypes:
                cases.append(_case("b9_uniform10", 4000 + seed, dtype=dtype))
                if len(cases) >= 32:
                    break
            seed += 1
        return cases
    raise ValueError(f"unknown row {row!r}")


# ---------------------------------------------------------------------------
# worker: execute one (op, row) in an isolated process (GPU)
# ---------------------------------------------------------------------------

def _load_kernel(kernel_path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("c6_kernel", kernel_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _encode_tensor(arr):
    import numpy as np
    arr = np.ascontiguousarray(arr)
    return {
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
        "data": base64.b64encode(arr.tobytes()).decode("ascii"),
    }


def _decode_tensor(t):
    import numpy as np
    arr = np.frombuffer(base64.b64decode(t["data"]), dtype=np.dtype(t["dtype"]))
    return arr.reshape(t["shape"]).copy()


def _fp64_reference(ref_path: Path, inputs_np: dict, timeout=120):
    payload = json.dumps({
        "inputs": {k: _encode_tensor(v) for k, v in inputs_np.items()},
        "kwargs": {},
    })
    proc = subprocess.run([PYBIN, str(ref_path)], input=payload,
                          capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"fp64 reference failed: {proc.stderr[-500:]}")
    return _decode_tensor(json.loads(proc.stdout))


def _sample_shapes(meta: dict, seed: int, variant: int) -> dict:
    """Deterministic shape assignment from the op schema's dim candidates."""
    import numpy as np
    schema = meta["op_schema"]
    rng = np.random.default_rng(
        int(hashlib.sha256(f"{meta['name']}|{seed}|{variant}".encode())
            .hexdigest()[:8], 16))
    dims = {}
    for dim in schema["dims"]:
        cands = dim["candidates"]
        dims[dim["name"]] = int(cands[int(rng.integers(len(cands)))])
    shapes = {}
    for item in schema["inputs"]:
        shapes[item["name"]] = tuple(dims[d] for d in item["dims"])
    return shapes


def _build_inputs(meta: dict, case: dict):
    import torch
    from src.stress.policy_bank import STRESS_POLICIES

    dtype_name = case["parameters"].get("dtype") or (meta.get("dtypes") or
                                                     ["float32"])[0]
    torch_dtype = getattr(torch, dtype_name)
    shapes = _sample_shapes(meta, case["seed"],
                            case["parameters"].get("shape_variant", 0))
    gen = torch.Generator().manual_seed(case["seed"])
    template = []
    names = list(meta.get("input_names") or shapes.keys())
    for name in names:
        template.append(torch.randn(shapes[name], generator=gen,
                                    dtype=torch.float32))
    policy = case["policy"]
    if policy == "iid":
        stressed = template
    elif policy == "b9_uniform10":
        stressed = [(torch.rand(t.shape,
                                generator=torch.Generator().manual_seed(
                                    case["seed"] + i))
                     * 2.0 - 1.0) * 10.0 for i, t in enumerate(template)]
    else:
        stressed = STRESS_POLICIES[policy](template, case["seed"])
    out = {}
    for name, tensor in zip(names, stressed):
        out[name] = tensor.to(torch_dtype).numpy()
    return out, dtype_name


def _compare(candidate, ideal, *, atol, rtol, absolute_only=False):
    import numpy as np
    if candidate.shape != ideal.shape:
        return False, f"shape {candidate.shape} != {ideal.shape}"
    if str(candidate.dtype) != str(ideal.dtype):
        return False, f"dtype {candidate.dtype} != {ideal.dtype}"
    c64 = candidate.astype(np.float64)
    i64 = ideal.astype(np.float64)
    nan_c, nan_i = np.isnan(c64), np.isnan(i64)
    if not np.array_equal(nan_c, nan_i):
        return False, "NaN pattern mismatch"
    mask = ~nan_c
    if absolute_only:
        ok = np.all(np.abs(c64[mask] - i64[mask]) <= atol)
        return bool(ok), None if ok else "abs tolerance exceeded"
    ok = np.allclose(c64[mask], i64[mask], atol=atol, rtol=rtol)
    return bool(ok), None if ok else "atol/rtol tolerance exceeded"


def cmd_worker(args):
    meta = json.loads(Path(args.meta).read_text(encoding="utf-8"))
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    kernel = _load_kernel(Path(args.kernel))
    ref_path = Path(args.ref)
    tolerances = meta.get("tolerances") or {}

    observations = []
    for case in cases:
        rec = {"case": case, "started_at": _now()}
        t0 = time.time()
        try:
            inputs_np, dtype_name = _build_inputs(meta, case)
            out = kernel.run({k: v.copy() for k, v in inputs_np.items()})
            if case["parameters"].get("repeated"):
                out2 = kernel.run({k: v.copy() for k, v in inputs_np.items()})
                import numpy as np
                if not np.array_equal(
                        np.nan_to_num(out.astype(np.float64), nan=1e308),
                        np.nan_to_num(out2.astype(np.float64), nan=1e308)):
                    rec.update(status="FAIL",
                               reason="nondeterministic self-divergence")
                    rec["wall_s"] = round(time.time() - t0, 3)
                    observations.append(rec)
                    continue
            ideal = _fp64_reference(ref_path, inputs_np)
            if args.oracle == "flat_legacy":
                atol = rtol = 1e-2
                absolute = False
            elif args.oracle == "b9_absolute":
                atol = float(tolerances.get(dtype_name, 1e-4))
                rtol = 0.0
                absolute = True
            else:  # corpus unified tolerances
                atol = rtol = float(tolerances.get(dtype_name, 1e-4))
                absolute = False
            ok, reason = _compare(out, ideal, atol=atol, rtol=rtol,
                                  absolute_only=absolute)
            rec.update(status="PASS" if ok else "FAIL", reason=reason,
                       dtype=dtype_name, atol=atol, rtol=rtol)
        except Exception as exc:  # noqa: BLE001 — per-case inconclusive
            rec.update(status="INCONCLUSIVE", reason=repr(exc)[:400])
        rec["wall_s"] = round(time.time() - t0, 3)
        observations.append(rec)

    Path(args.out).write_text(
        "\n".join(json.dumps(o, sort_keys=True, default=str)
                  for o in observations) + "\n",
        encoding="utf-8")
    statuses = {}
    for o in observations:
        statuses[o["status"]] = statuses.get(o["status"], 0) + 1
    print(json.dumps({"op": meta.get("name"), "row": args.row,
                      "statuses": statuses}))


# ---------------------------------------------------------------------------
# driver: ops x rows, subprocess isolation, resume, aggregation
# ---------------------------------------------------------------------------

ROWS = ["b1-flat-legacy", "b1u", "b3-iid32", "b4-value", "b5-boundary",
        "b6-context", "m-full", "m-dir", "b7-port", "b8-port", "b9-port"]
ORACLE_BY_ROW = {"b1-flat-legacy": "flat_legacy", "b9-port": "b9_absolute"}


def cmd_drive(args):
    data_dir = None
    for cand in Path(args.corpus_root).rglob("gpuemu_corpus/data"):
        data_dir = cand
        break
    if data_dir is None:
        raise SystemExit(f"corpus data dir not found under {args.corpus_root}")

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    ledger = out_root / "c6_campaign_ledger.jsonl"

    ops = sorted(p for p in data_dir.iterdir()
                 if p.is_dir() and (p / "meta.json").is_file())
    print(f"[{_now()}] C6 campaign: {len(ops)} ops x {len(ROWS)} rows",
          flush=True)

    for op_dir in ops:
        meta = json.loads((op_dir / "meta.json").read_text(encoding="utf-8"))
        op_name = op_dir.name
        kernel_path = op_dir / "kernel.py"
        ref_path = data_dir / str(meta.get("reference",
                                           f"{op_name}/ref_fp64.py"))
        kernel_source = kernel_path.read_text(encoding="utf-8",
                                              errors="replace")
        for row in ROWS:
            obs_path = out_root / f"{op_name}__{row}.jsonl"
            if obs_path.exists():
                continue
            cases = build_row_cases(row, meta, kernel_source, op_name)
            cases_path = out_root / f"_cases_{op_name}__{row}.json"
            cases_path.write_text(json.dumps(cases), encoding="utf-8")
            record = {"op": op_name, "row": row, "cases": len(cases),
                      "started_at": _now()}
            t0 = time.time()
            proc = subprocess.run(
                [PYBIN, "-u", os.path.abspath(__file__), "worker",
                 "--meta", str(op_dir / "meta.json"),
                 "--kernel", str(kernel_path),
                 "--ref", str(ref_path),
                 "--cases", str(cases_path),
                 "--row", row,
                 "--oracle", ORACLE_BY_ROW.get(row, "corpus_unified"),
                 "--out", str(obs_path)],
                capture_output=True, text=True, timeout=args.timeout,
                cwd=str(MK))
            record["exit_code"] = proc.returncode
            record["wall_s"] = round(time.time() - t0, 2)
            if proc.returncode != 0:
                record["status"] = "worker_crash"
                record["stderr_tail"] = (proc.stderr or "")[-1500:]
                obs_path.write_text(json.dumps({
                    "status": "ROW_INCONCLUSIVE",
                    "reason": "worker crash",
                    "stderr_tail": (proc.stderr or "")[-1500:],
                }) + "\n", encoding="utf-8")
            else:
                record["status"] = "ok"
                record["stdout_tail"] = (proc.stdout or "").strip()[-300:]
            with open(ledger, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, sort_keys=True) + "\n")
            print(f"[{_now()}] {op_name} x {row}: {record['status']} "
                  f"({record['wall_s']}s)", flush=True)

    # aggregate Table 9 raw matrix
    agg = {}
    for op_dir in ops:
        op_name = op_dir.name
        label = ("seeded_bug" if op_name.endswith("_buggy")
                 else "correct_control")
        agg[op_name] = {"third_party_label": label, "rows": {}}
        for row in ROWS:
            obs_path = out_root / f"{op_name}__{row}.jsonl"
            statuses = {}
            with open(obs_path, encoding="utf-8") as fh:
                for line in fh:
                    rec = json.loads(line)
                    st = rec.get("status", "ROW_INCONCLUSIVE")
                    statuses[st] = statuses.get(st, 0) + 1
            if statuses.get("FAIL"):
                verdict = "detected"
            elif statuses.get("ROW_INCONCLUSIVE") or (
                    statuses.get("INCONCLUSIVE") and not statuses.get("PASS")):
                verdict = "inconclusive"
            else:
                verdict = "pass"
            agg[op_name]["rows"][row] = {"verdict": verdict, **statuses}
    (out_root / "c6_table9_raw.json").write_text(
        json.dumps({"generated_at": _now(), "ops": agg}, indent=1,
                   sort_keys=True), encoding="utf-8")
    print(f"[{_now()}] aggregation written: c6_table9_raw.json", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)

    d = sub.add_parser("drive")
    d.add_argument("--corpus-root", required=True, type=Path)
    d.add_argument("--out-dir", required=True, type=Path)
    d.add_argument("--timeout", type=int, default=1800)
    d.set_defaults(func=cmd_drive)

    w = sub.add_parser("worker")
    w.add_argument("--meta", required=True)
    w.add_argument("--kernel", required=True)
    w.add_argument("--ref", required=True)
    w.add_argument("--cases", required=True)
    w.add_argument("--row", required=True)
    w.add_argument("--oracle", required=True)
    w.add_argument("--out", required=True)
    w.set_defaults(func=cmd_worker)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
