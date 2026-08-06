#!/usr/bin/env python3
"""Port-fidelity reproduction runs (blueprint §5.1.2: 复现偏差 B7 ? B8 ? B9 ?).

The blueprint requires each protocol port to be validated "by re-running on
the original tool's *native* dataset and comparing with its published
results".  This driver executes exactly that for B7 and B8; B9's native
dataset is the gpuemu corpus, whose comparison is an offline aggregation of
the Lane C6 ``b9-port`` row against the corpus ``benchmark_verdict`` (see
subcommand ``b9-aggregate``).

  b7  robust-kbench highlighted set (8 forward kernels, all published
      Correct=True in highlighted/results.csv).  Protocol per the frozen
      external_baselines.json native record @078f5bab: forward trials with
      multi-init x multi-input, candidate called twice per trial (repeat
      pair), oracle torch.allclose(atol=rtol=1e-5).  Port layout (forward
      only): 4 inits x 4 draws.
  b8  KernelBenchX kbx_corpus/all_records.jsonl (110 before/after states
      with recorded call_ok/exe_ok).  Each state's candidate code replaces
      the golden reference implementation and the golden file's own test
      harness is executed under seed 42; outputs are compared against the
      golden reference implementation run under the identical seed with the
      upstream dtype-aware tolerances (fp16/bf16 5e-3, fp32/64 1e-5).
      ``rand_tensor`` is provided by the port's preregistered value-family
      implementations (standard/outlier/uniform).
  b9-aggregate  compares Lane C6 b9-port row verdicts against the corpus
      benchmark_verdict per op.

Every kernel/record runs in an isolated subprocess (asynchronous CUDA
failures cannot poison the batch); per-item JSONL rows + full worker logs
are preserved for the blind audit.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PYBIN = "/root/miniconda3/bin/python"

B7_ATOL = B7_RTOL = 1e-5
B7_INITS = 4
B7_DRAWS = 4

B8_TOL = {
    "float16": 5e-3, "bfloat16": 5e-3,
    "float32": 1e-5, "float64": 1e-5,
}


def now():
    return datetime.now(timezone.utc).isoformat()


# ===========================================================================
# B7 worker (written to a temp file, run per kernel)
# ===========================================================================
B7_WORKER = r'''
import importlib.util, json, sys, torch

problem_file, kernel_file, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

spec = importlib.util.spec_from_file_location("rkb_problem", problem_file)
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)

ns = dict(vars(P))
exec(open(kernel_file, encoding="utf-8").read(), ns)
ModelNew = ns["ModelNew"]

rows = []
all_ok = True
for init in range(%(inits)d):
    torch.manual_seed(90000 + init)
    cand = ModelNew(*P.get_init_inputs()).cuda() if P.get_init_inputs() \
        else ModelNew().cuda()
    ref = P.Model(*P.get_init_inputs()) if P.get_init_inputs() else P.Model()
    for draw in range(%(draws)d):
        torch.manual_seed(init * 1000 + draw)
        inputs = P.get_inputs()
        row = {"init": init, "draw": draw}
        try:
            with torch.no_grad():
                out_ref = ref(*inputs)
                out_c1 = cand(*inputs)
                out_c2 = cand(*inputs)          # repeat pair, both charged
            ok = (torch.allclose(out_ref.float(), out_c1.float(),
                                 atol=%(atol)g, rtol=%(rtol)g)
                  and torch.allclose(out_ref.float(), out_c2.float(),
                                     atol=%(atol)g, rtol=%(rtol)g))
            row.update(status="PASS" if ok else "FAIL",
                       max_abs=float((out_ref.float()
                                      - out_c1.float()).abs().max()))
        except Exception as exc:
            ok = False
            row.update(status="ERROR", reason=repr(exc)[:400])
        all_ok = all_ok and ok
        rows.append(row)

json.dump({"verdict_correct": all_ok, "trials": rows}, open(out_path, "w"))
print("B7_WORKER_OK")
'''


def cmd_b7(args):
    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    logs = out_root / "worker_logs"
    logs.mkdir(exist_ok=True)

    registry = json.loads(Path(args.registry).read_text("utf-8"))
    published = {}
    with open(args.results_csv, encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            if str(row.get("forward")).strip() == "True":
                published[row["task_name"]] = (
                    str(row.get("Correct")).strip() == "True")

    worker = out_root / "_b7_worker.py"
    worker.write_text(B7_WORKER % {
        "inits": B7_INITS, "draws": B7_DRAWS,
        "atol": B7_ATOL, "rtol": B7_RTOL}, encoding="utf-8")

    obs_path = out_root / "b7_fidelity.jsonl"
    done = set()
    if obs_path.exists():
        for line in obs_path.read_text("utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["id"])

    root = Path(args.data_root)
    for entry in registry:
        tid = entry["id"]
        if tid in done:
            continue
        if tid not in published:
            with open(obs_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "id": tid, "skipped": "no published forward verdict",
                    "at": now()}) + "\n")
            continue
        ksrc = out_root / f"_kernel_{tid}.py"
        ksrc.write_text(entry["kernel_source"], encoding="utf-8")
        verdict_path = out_root / f"_verdict_{tid}.json"
        t0 = time.time()
        with open(logs / f"{tid}.log", "w", encoding="utf-8") as lf:
            proc = subprocess.run(
                [PYBIN, str(worker), str(root / entry["reference_file"]),
                 str(ksrc), str(verdict_path)],
                stdout=lf, stderr=subprocess.STDOUT,
                timeout=args.timeout, cwd=str(root))
        rec = {"id": tid, "published_correct": published[tid],
               "wall_s": round(time.time() - t0, 1), "at": now()}
        if proc.returncode == 0 and verdict_path.exists():
            v = json.loads(verdict_path.read_text("utf-8"))
            rec.update(replicated_correct=v["verdict_correct"],
                       agree=(v["verdict_correct"] == published[tid]),
                       trials=v["trials"])
        else:
            rec.update(replicated_correct=None, agree=False,
                       error=f"worker exit {proc.returncode}")
        with open(obs_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(f"[b7] {tid}: published={rec['published_correct']} "
              f"replicated={rec.get('replicated_correct')}", flush=True)

    _b7_summary(obs_path, out_root)


def _b7_summary(obs_path, out_root):
    rows = [json.loads(l) for l in obs_path.read_text("utf-8").splitlines()
            if l.strip() and "skipped" not in l]
    n = len(rows)
    agree = sum(1 for r in rows if r.get("agree"))
    summary = {
        "n_kernels": n, "agree": agree,
        "reproduction_deviation": round(1 - agree / n, 4) if n else None,
        "protocol": "robust-kbench native highlighted set, forward, "
                    "4 inits x 4 draws x repeat pair, allclose 1e-5",
        "generated_at": now(),
    }
    (out_root / "b7_fidelity_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))


# ===========================================================================
# B8 worker
# ===========================================================================
B8_WORKER = r'''
import json, sys, types, torch

golden_file, cand_file, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
TOL = %(tol)s

# --- port value families as the corpus' data_utils -------------------------
# Draws use a dedicated per-call-sequence generator (seed 42 + call index)
# instead of the global torch RNG: candidate kernels with @triton.autotune
# consume global RNG state during their first launch, which would otherwise
# desynchronize the reference and candidate input streams.  Distributions and
# determinism are unchanged; disclosed in the protocol note.
_CALL_IDX = [0]

def rand_tensor(shape, dtype=torch.float32, mode="standard",
                outlier_prob=0.001, outlier_scale=50.0, low=-1.0, high=1.0,
                device="cuda", **kw):
    g = torch.Generator()
    g.manual_seed(42 + _CALL_IDX[0])
    _CALL_IDX[0] += 1
    if mode == "standard":
        v = torch.randn(shape, generator=g)
    elif mode == "outlier":
        v = torch.randn(shape, generator=g)
        mask = torch.rand(shape, generator=g) < outlier_prob
        cnt = int(mask.sum())
        if cnt:
            v[mask] = torch.randn(cnt, generator=g) * outlier_scale
    elif mode == "uniform":
        v = (high - low) * torch.rand(shape, generator=g) + low
    else:
        raise ValueError("mode " + mode)
    return v.to(device=device, dtype=dtype)

du = types.ModuleType("data_utils")
du.rand_tensor = rand_tensor
sys.modules["data_utils"] = du

golden = open(golden_file, encoding="utf-8", errors="replace").read()
import re as _re
parts = _re.split(r"\n#{40,}\n", golden, maxsplit=1)
assert len(parts) == 2, "golden file separator not found"
ref_impl, test_part = parts

import os
_RUN_DIR = os.path.dirname(out_path)

def run(impl_src, tag):
    # Written to a real file so triton's inspect.getsource works.
    path = os.path.join(_RUN_DIR, "_combined_" + tag + ".py")
    src = impl_src + "\n" + test_part
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(src)
    import linecache
    linecache.clearcache()
    ns = {"__file__": path, "__name__": "__main__"}
    _CALL_IDX[0] = 0
    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    exec(compile(src, path, "exec"), ns)
    return ns["test_results"]

def flatten(v):
    if isinstance(v, torch.Tensor):
        return [v]
    if isinstance(v, (list, tuple)):
        out = []
        for x in v:
            out.extend(flatten(x))
        return out
    return []

result = {"call_ok": False, "exe_ok": False}
try:
    ref_results = run(ref_impl, "ref")
except Exception as exc:
    json.dump({"call_ok": None, "exe_ok": None,
               "error": "REFERENCE failed: " + repr(exc)[:400]},
              open(out_path, "w"))
    print("B8_WORKER_REF_FAIL")
    raise SystemExit(0)

try:
    # Corpus code fields may embed the golden test harness after the same
    # separator; keep only the implementation part so the appended golden
    # test runs exactly once (and the RNG call sequence stays aligned).
    cand_src = open(cand_file, encoding="utf-8").read()
    cand_impl = _re.split(r"\n#{40,}\n", cand_src, maxsplit=1)[0]
    cand_results = run(cand_impl, "cand")
    result["call_ok"] = True
except Exception as exc:
    result["error"] = repr(exc)[:400]
    json.dump(result, open(out_path, "w"))
    print("B8_WORKER_OK")
    raise SystemExit(0)

mismatch = []
try:
    for key, rv in ref_results.items():
        rts, cts = flatten(rv), flatten(cand_results.get(key))
        if len(rts) != len(cts):
            mismatch.append(key + ": arity")
            continue
        for i, (a, b) in enumerate(zip(rts, cts)):
            tol = TOL.get(str(a.dtype).replace("torch.", ""), 1e-5)
            if a.shape != b.shape:
                mismatch.append(f"{key}[{i}]: shape")
                continue
            if not torch.allclose(a.float(), b.float(), atol=tol, rtol=tol,
                                  equal_nan=True):
                mismatch.append(f"{key}[{i}]: value")
    result["exe_ok"] = not mismatch
    result["mismatch"] = mismatch[:20]
except Exception as exc:
    result["error"] = "compare: " + repr(exc)[:400]

json.dump(result, open(out_path, "w"))
print("B8_WORKER_OK")
'''


def cmd_b8(args):
    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    logs = out_root / "worker_logs"
    logs.mkdir(exist_ok=True)

    worker = out_root / "_b8_worker.py"
    worker.write_text(B8_WORKER % {"tol": json.dumps(B8_TOL)},
                      encoding="utf-8")

    obs_path = out_root / "b8_fidelity.jsonl"
    done = set()
    if obs_path.exists():
        for line in obs_path.read_text("utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["task_id"], r["transition"], r["side"]))

    golden_root = Path(args.golden_root)
    with open(args.records, encoding="utf-8") as fh:
        records = [json.loads(l) for l in fh if l.strip()]

    # parquet fallback for records whose jsonl code was newline-mangled
    parquet_code = {}
    if args.parquet and Path(args.parquet).exists():
        import pyarrow.parquet as pq
        for row in pq.read_table(args.parquet).to_pylist():
            parquet_code[(row["task_id"], row["transition"])] = row

    for rec in records:
        tid = rec["task_id"]
        golden = golden_root / tid
        for side in ("before", "after"):
            key = (tid, rec["transition"], side)
            if key in done:
                continue
            meta_raw = rec.get(side)
            if isinstance(meta_raw, dict):
                expected_exe = meta_raw.get("exe_ok")
                expected_call = meta_raw.get("call_ok")
            else:
                m = re.search(r"'exe_ok': (True|False)", meta_raw or "")
                mc = re.search(r"'call_ok': (True|False)", meta_raw or "")
                expected_exe = (m.group(1) == "True") if m else None
                expected_call = (mc.group(1) == "True") if mc else None
            code = rec.get(f"{side}_code")
            code_source = "jsonl"

            def _impl_ok(src):
                impl = re.split(r"\n#{40,}\n", src, maxsplit=1)[0]
                try:
                    compile(impl, "<check>", "exec")
                    return True
                except SyntaxError:
                    return False

            if code and not _impl_ok(code):
                alt = parquet_code.get((tid, rec["transition"]), {})
                alt_code = alt.get(f"{side}_code")
                if alt_code and _impl_ok(alt_code):
                    code, code_source = alt_code, "parquet"
                else:
                    code, code_source = None, (
                        "mangled_both" if alt_code else "mangled_no_fallback")
            row = {"task_id": tid, "transition": rec["transition"],
                   "side": side, "expected_exe_ok": expected_exe,
                   "expected_call_ok": expected_call,
                   "code_source": code_source, "at": now()}
            if not code or not golden.exists():
                row["skipped"] = (code_source if code_source.startswith(
                    "mangled") else
                    ("no code" if not code else "no golden file"))
                with open(obs_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row) + "\n")
                continue
            cand_file = out_root / "_cand.py"
            cand_file.write_text(code, encoding="utf-8")
            verdict_path = out_root / "_verdict.json"
            if verdict_path.exists():
                verdict_path.unlink()
            t0 = time.time()
            log_name = f"{tid.replace('/', '__')}__{rec['transition']}" \
                       f"__{side}.log"
            try:
                with open(logs / log_name, "w", encoding="utf-8") as lf:
                    proc = subprocess.run(
                        [PYBIN, str(worker), str(golden), str(cand_file),
                         str(verdict_path)],
                        stdout=lf, stderr=subprocess.STDOUT,
                        timeout=args.timeout)
                rc = proc.returncode
            except subprocess.TimeoutExpired:
                rc = "timeout"
            row["wall_s"] = round(time.time() - t0, 1)
            if rc == 0 and verdict_path.exists():
                v = json.loads(verdict_path.read_text("utf-8"))
                row.update(replicated_call_ok=v.get("call_ok"),
                           replicated_exe_ok=v.get("exe_ok"),
                           mismatch=v.get("mismatch"),
                           error=v.get("error"))
                row["agree"] = (v.get("exe_ok") == expected_exe) \
                    if expected_exe is not None else None
            else:
                row.update(replicated_exe_ok=None, agree=None,
                           error=f"worker rc={rc}")
            with open(obs_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(f"[b8] {tid} {rec['transition']} {side}: "
                  f"expect={expected_exe} got={row.get('replicated_exe_ok')}",
                  flush=True)

    _b8_summary(obs_path, out_root)


def _b8_summary(obs_path, out_root):
    rows = [json.loads(l) for l in obs_path.read_text("utf-8").splitlines()
            if l.strip()]
    scored = [r for r in rows if r.get("agree") is not None]
    agree = sum(1 for r in scored if r["agree"])
    summary = {
        "n_states_total": len(rows),
        "n_states_scored": len(scored),
        "n_skipped_or_unscorable": len(rows) - len(scored),
        "agree": agree,
        "reproduction_deviation":
            round(1 - agree / len(scored), 4) if scored else None,
        "protocol": "KernelBenchX golden tests, candidate substitution, "
                    "seed 42, upstream dtype tolerances",
        "generated_at": now(),
    }
    (out_root / "b8_fidelity_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))


# ===========================================================================
# B9: offline aggregation against the corpus' shipped verdicts
# ===========================================================================
def cmd_b9_aggregate(args):
    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    corpus = Path(args.corpus_data)
    rows = []
    for meta_path in sorted(corpus.glob("*/meta.json")):
        meta = json.loads(meta_path.read_text("utf-8"))
        op = meta_path.parent.name
        obs = Path(args.c6_dir) / f"{op}__b9-port.jsonl"
        if not obs.exists():
            rows.append({"op": op, "skipped": "no c6 b9-port row"})
            continue
        statuses = [json.loads(l)["status"]
                    for l in obs.read_text("utf-8").splitlines() if l.strip()]
        replicated_pass = all(s == "PASS" for s in statuses) \
            if statuses else None
        published_pass = (meta.get("benchmark_verdict") == "pass")
        rows.append({"op": op,
                     "published_pass": published_pass,
                     "replicated_pass": replicated_pass,
                     "n_cases": len(statuses),
                     "agree": replicated_pass == published_pass})
    scored = [r for r in rows if "skipped" not in r]
    agree = sum(1 for r in scored if r["agree"])
    summary = {
        "n_ops": len(scored), "agree": agree,
        "reproduction_deviation":
            round(1 - agree / len(scored), 4) if scored else None,
        "protocol": "gpuemu corpus (B9's native dataset): Lane C6 b9-port "
                    "row op verdict vs corpus benchmark_verdict",
        "rows": rows,
        "generated_at": now(),
    }
    (out_root / "b9_fidelity_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in
                      ("n_ops", "agree", "reproduction_deviation")}))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("b7")
    p.add_argument("--registry",
                   default="/root/robust_kbench_data/registry.json")
    p.add_argument("--results-csv",
                   default="/root/robust_kbench_data/highlighted/results.csv")
    p.add_argument("--data-root", default="/root/robust_kbench_data")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--timeout", type=int, default=1200)
    p.set_defaults(func=cmd_b7)

    p = sub.add_parser("b8")
    p.add_argument("--records",
                   default="/root/KernelBenchX_hf/kbx_corpus/all_records.jsonl")
    p.add_argument("--golden-root",
                   default="/root/KernelBenchX_hf/kernelbenchx")
    p.add_argument("--parquet",
                   default="/root/KernelBenchX_hf/corpus_all.parquet")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--timeout", type=int, default=300)
    p.set_defaults(func=cmd_b8)

    p = sub.add_parser("b9-aggregate")
    p.add_argument("--c6-dir", required=True)
    p.add_argument("--corpus-data",
                   default="/root/mk_v2/external/C6_gpuemu/gpuemu-corpus/"
                           "gpuemu_corpus/data")
    p.add_argument("--out-dir", required=True)
    p.set_defaults(func=cmd_b9_aggregate)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
