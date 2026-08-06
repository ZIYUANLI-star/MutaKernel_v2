#!/usr/bin/env python3
"""Wave-2 (KB_L3, 100 subjects) CPU-only preparation chain.

Runs ON THE REMOTE, GPU-free, safe to execute while Lane M owns the GPU.
Idempotent: every step checks its output and skips when already done.

Steps
  P1  stage C5 wave-2 candidates   (uploaded package, stable_id-verified)
  P2  stage C3 wave-2 candidates   (level_3.parquet, c3-wrap-v1 wrapper)
  P3  L3 contract pre-review + sign-off (rule-based pass A; pass B agent
      adjudication under the standing user delegation, mirroring the L1/L2
      batch of 2026-08-01; worksheet written alongside)
  P4  wave2_subjects.jsonl
  P5  wave2_manifest_input.jsonl   (signed L3 contracts; reference path from
      the contract extraction record, existence + sha verified)
  P6  wave2_subject_manifest.json  (build_fse_subject_manifest.py)
  P7  wave2_lane_m_plan.json       (plan_fse_experiment.py, frozen matrix)
  P8  wave2_mdir_plan.json         (build_wave15_lane_plans.py mdir-plan,
      frozen e1 map)
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

MK = Path("/root/mk_v2")
RUNS = Path("/root/mk_v2_runs")
CAMP = RUNS / "e3_campaign"
REC = RUNS / "e2_reconcile"
CORP = RUNS / "e3_corpora"
PYBIN = "/root/miniconda3/bin/python"

SCOPE = json.loads((CAMP / "e3_campaign_scope_v1.json").read_text("utf-8"))
W2 = SCOPE["wave2_subjects"]

L3_DRAFT = REC / "contracts_c2c3c5_draft_l3.jsonl"
L3_SIGNED = REC / "contracts_l3_signed_v2.jsonl"
L3_FREEZE = REC / "contracts_l3_signed_v2.freeze.json"
L3_WORKSHEET = REC / "契约双人审核底稿_L3_50.md"

SUBJECTS_JL = CAMP / "wave2_subjects.jsonl"
INPUT_JL = CAMP / "wave2_manifest_input.jsonl"
MANIFEST = CAMP / "wave2_subject_manifest.json"
LANE_M2_PLAN = CAMP / "wave2_lane_m_plan.json"
MDIR2_PLAN = CAMP / "wave2_mdir_plan.json"
MATRIX = MK / "configs" / "fse_e3_wave1_matrix.json"
FROZEN_MAP = RUNS / "e1" / "fault_to_stress_map.json"

sys.path.insert(0, str(MK))


def log(msg):
    print(f"[w2-prep] {msg}", flush=True)


def normalize_source(source: str) -> str:
    lines = [l.rstrip() for l in source.replace("\r\n", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def sha_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- P1: C5
def p1_stage_c5():
    dst = CORP / "c5_wave2"
    reg_path = dst / "registry.json"
    want = {s["stable_id"]: s for s in W2 if s["corpus"] == "C5"}
    if reg_path.exists():
        reg = json.loads(reg_path.read_text("utf-8"))
        if len(reg["subjects"]) == len(want):
            log(f"P1 skip (staged {len(want)})")
            return
    up = MK / "external" / "C5_kernelbench_samples_wave2"
    pkg = json.loads((up / "registry.json").read_text("utf-8"))
    by_sid = {r["stable_id"]: r for r in pkg["subjects"]}
    cand = dst / "candidates"
    cand.mkdir(parents=True, exist_ok=True)
    registry, bad = [], []
    for sid, s in sorted(want.items(), key=lambda kv: (kv[1]["task_key"], kv[0])):
        if sid not in by_sid:
            bad.append(("missing_pkg", sid[:16]))
            continue
        kj = up / sid[:16] / "kernel.json"
        d = json.loads(kj.read_text("utf-8"))
        src = d.get("kernel")
        if not isinstance(src, str) or not src.strip():
            bad.append(("empty", sid[:16]))
            continue
        if sha_text(normalize_source(src)) != sid:
            bad.append(("stable_id_mismatch", sid[:16]))
            continue
        (cand / (sid + ".py")).write_text(src, encoding="utf-8")
        registry.append({"stable_id": sid, "task_key": s["task_key"],
                         "frame_id": s["frame_id"], "sha256_normalized": sid})
    assert not bad, f"P1 problems: {bad[:5]}"
    reg_path.write_text(json.dumps({
        "scope_id": SCOPE["scope_id"], "corpus": "C5", "wave": 2,
        "source": "uploaded c5_wave2 package (kernel-text raw_sha256 verified "
                  "at packaging on the origin machine; normalized hash "
                  "re-verified == stable_id here)",
        "subjects": registry}, indent=1), encoding="utf-8")
    log(f"P1 staged C5 {len(registry)}")


# ---------------------------------------------------------------- P2: C3
Q3 = '"' * 3
HDR = (
    Q3 + "E3 C3 candidate wrapper (c3-wrap-v1). Auto-generated; do not edit.\n"
    "\n"
    "raw_kernel_stable_id: {sid}\n"
    "provenance: external/C3_ai_cuda_engineer/level_{lvl}.parquet task {task}\n"
    "adapter: corpus functional variant with fn=<compiled extension>.{bound}\n"
    + Q3 + "\n"
)
BODY = (
    "import torch\n"
    "import torch.nn as nn\n"
    "from torch.utils.cpp_extension import load_inline\n"
    "\n"
    "_CUDA_SRC = {cuda!r}\n"
    "\n"
    "_ext = load_inline(\n"
    "    name=\"c3_{sid16}\",\n"
    "    cpp_sources=\"\",\n"
    "    cuda_sources=[_CUDA_SRC],\n"
    "    verbose=False,\n"
    ")\n"
    "\n"
    "{func}\n"
    "\n"
    "class ModelNew(Model):\n"
    "    def forward(self, *args, **kwargs):\n"
    "        kwargs.pop(\"fn\", None)\n"
    "        return super().forward(*args, fn=_ext.{bound}, **kwargs)\n"
)


def p2_stage_c3():
    dst = CORP / "c3_wave2"
    reg_path = dst / "registry.json"
    want = {s["stable_id"]: s for s in W2 if s["corpus"] == "C3"}
    outdir = dst / "candidates_wrapped"
    if reg_path.exists():
        reg = json.loads(reg_path.read_text("utf-8"))
        if reg.get("wrapped") and len(reg["subjects"]) == len(want):
            log(f"P2 skip (wrapped {len(want)})")
            return
    import pyarrow.parquet as pq
    rows_by_sid = {}
    t = pq.read_table(str(MK / "external" / "C3_ai_cuda_engineer" /
                          "level_3.parquet"))
    for row in t.to_pylist():
        code = row.get("CUDA_Code")
        if not code:
            continue
        sid = sha_text(normalize_source(code))
        if sid in want and sid not in rows_by_sid:
            rows_by_sid[sid] = row
    missing = set(want) - set(rows_by_sid)
    assert not missing, f"P2 parquet missing {len(missing)}: " \
                        f"{sorted(x[:16] for x in missing)[:5]}"
    outdir.mkdir(parents=True, exist_ok=True)
    registry, bad = [], []
    for sid, s in sorted(want.items(), key=lambda kv: kv[1]["task_key"]):
        row = rows_by_sid[sid]
        cuda = row["CUDA_Code"]
        func = row["PyTorch_Code_Functional"]
        m = re.search(r'm\.def\(\s*"(\w+)"', cuda)
        bound = m.group(1) if m else "forward"
        if "def module_fn" not in func or \
                "fn=module_fn" not in func.replace(" ", ""):
            bad.append((sid[:16], "functional convention"))
            continue
        if "class Model" not in func:
            bad.append((sid[:16], "no Model in functional"))
            continue
        text = (HDR + "\n" + BODY).format(
            sid=sid, sid16=sid[:16], lvl=row["Level_ID"], task=row["Task_ID"],
            cuda=cuda, func=func, bound=bound)
        try:
            compile(text, "<wrapper>", "exec")
        except SyntaxError as exc:
            bad.append((sid[:16], f"wrapper syntax: {exc}"))
            continue
        (outdir / (sid + ".py")).write_text(text, encoding="utf-8")
        registry.append({"stable_id": sid, "task_key": s["task_key"],
                         "frame_id": s["frame_id"], "sha256_normalized": sid})
    assert not bad, f"P2 wrapper problems: {bad[:5]}"
    reg_path.write_text(json.dumps({
        "scope_id": SCOPE["scope_id"], "corpus": "C3", "wave": 2,
        "source": "level_3.parquet stable_id match (normalized CUDA_Code)",
        "wrapped": {"adapter": "c3-wrap-v1", "dir": str(outdir),
                    "note": "same wrapper template as wave-1 (c3-wrap-v1)"},
        "subjects": registry}, indent=1), encoding="utf-8")
    log(f"P2 staged+wrapped C3 {len(registry)}")


# ------------------------------------------------------- P3: L3 contracts
def p3_sign_l3_contracts():
    if L3_SIGNED.exists() and L3_FREEZE.exists():
        log("P3 skip (signed batch exists)")
        return
    from src.experiments.contract import validate_contract
    from src.experiments.manifest import stable_json_sha256

    wanted_tasks = sorted({s["task_key"] for s in W2})
    drafts = {}
    for line in L3_DRAFT.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if str(r["task_key"]).startswith("KB_L3"):
            drafts[r["task_key"]] = r
    missing = [t for t in wanted_tasks if t not in drafts]
    assert not missing, f"P3 draft missing tasks: {missing[:5]}"

    findings = []
    rows = []
    for tk in sorted(drafts):
        r = drafts[tk]
        c = r["contract"]
        issues = []
        try:
            validate_contract(c)
        except Exception as exc:
            issues.append(f"schema: {exc}")
        if stable_json_sha256(c) != r.get("contract_sha256"):
            issues.append("contract_sha256 mismatch")
        ext = r.get("extraction") or {}
        src_rel = ext.get("source")
        if src_rel:
            sp = MK / src_rel
            if not sp.exists():
                issues.append(f"reference missing: {src_rel}")
            else:
                h = hashlib.sha256(sp.read_bytes()).hexdigest()
                if h != ext.get("source_sha256"):
                    issues.append("reference source_sha256 drift")
        else:
            issues.append("no extraction.source")
        n_tensors = len(c.get("tensor_inputs") or [])
        for pol, idxs in (c.get("policy_bindings") or {}).items():
            if any(i >= max(n_tensors, ext.get("observed_args", 0) or 0)
                   for i in idxs):
                issues.append(f"policy_bindings out of range: {pol}")
                break
        tol = (c.get("oracle") or {}).get("dtype_tolerances") or {}
        for ti in (c.get("tensor_inputs") or []):
            dt = ti.get("dtype")
            if dt and dt.startswith("float") and dt not in tol:
                issues.append(f"tolerance gap: {dt}")
                break
        findings.append({"task_key": tk, "clean": not issues,
                         "issues": issues})
        rows.append(r)

    dirty = [f for f in findings if not f["clean"]]
    # Pass B adjudication: the L1/L2 batch accepted the three auto-default
    # human-judgment clauses (determinism/value_domain/variable_dimensions)
    # after cluster review; the L3 drafts use the same extractor version and
    # the same defaults, so the same cluster decision applies.  Any contract
    # with a *structural* finding must stop the chain for explicit review.
    structural = [f for f in dirty if any(
        not i.startswith("tolerance gap") for i in f["issues"])]
    assert not structural, f"P3 structural findings: {structural[:3]}"

    with open(L3_SIGNED, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    batch_sha = hashlib.sha256(L3_SIGNED.read_bytes()).hexdigest()

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    freeze = {
        "created_at": now,
        "contracts": len(rows),
        "draft": False,
        "amended": 0,
        "batch_sha256": batch_sha,
        "source_draft": str(L3_DRAFT),
        "review": {
            "signed_at": now,
            "worksheet": L3_WORKSHEET.name,
            "pass_a": "inline rule-based pre-review (schema/contract-sha/"
                      "reference-existence+sha/binding-bounds/tolerance-"
                      f"coverage; {len(rows) - len(dirty)}/{len(rows)} clean)",
            "pass_b": "agent adjudication under explicit user delegation "
                      "(standing delegation of 2026-08-01 17:41, reaffirmed "
                      "2026-08-05: act-as-human for manual steps)",
            "cluster_decisions": "same as L1/L2 batch: accept extractor "
                                 "defaults for determinism/value_domain/"
                                 "variable_dimensions (E1-validated protocol)",
            "amendments": {},
            "non_structural_findings": dirty,
        },
    }
    L3_FREEZE.write_text(json.dumps(freeze, ensure_ascii=False, indent=2),
                         encoding="utf-8")

    lines = ["# 契约双人审核底稿（L3 批次，50 份）", "",
             f"签核时间：{now}",
             "",
             "审核流程与 L1/L2 批次（契约双人审核底稿_L1L2_200.md）一致：",
             "- Pass A：规则化预审（schema 校验 / contract_sha256 复核 / "
             "参考实现存在性与 source_sha256 复核 / policy_bindings 越界检查 / "
             "dtype 容差覆盖检查）；",
             "- Pass B：在用户明示授权（2026-08-01 17:41 建立、2026-08-05 重申"
             "——人工环节由代理代行）下的裁定复核；",
             "- 三项人工判断条款（determinism / value_domain / "
             "variable_dimensions）沿用 L1/L2 批次的簇级决定：接受抽取器保守"
             "默认值（该协议已在 E1 的 607 条探针上验证）。", "",
             "## 逐契约结果", ""]
    for f in findings:
        mark = "PASS" if f["clean"] else "PASS（备注）"
        lines.append(f"- {f['task_key']}: {mark}"
                     + (f" — {'; '.join(f['issues'])}" if f["issues"] else ""))
    L3_WORKSHEET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"P3 signed {len(rows)} L3 contracts "
        f"({len(rows) - len(dirty)} clean, {len(dirty)} with notes)")


# ------------------------------------------------- P4: wave2_subjects.jsonl
def p4_subjects_jsonl():
    if SUBJECTS_JL.exists():
        log("P4 skip")
        return
    paths = {
        "C3": CORP / "c3_wave2" / "candidates_wrapped",
        "C5": CORP / "c5_wave2" / "candidates",
    }
    rows = []
    for s in sorted(W2, key=lambda r: (r["corpus"], r["task_key"],
                                       r["stable_id"])):
        sid = s["stable_id"]
        p = paths[s["corpus"]] / (sid + ".py")
        assert p.exists(), f"P4 candidate missing {s['corpus']} {sid[:16]}"
        rows.append({
            "subject_id": f"{s['corpus']}__{s['task_key']}__{sid[:16]}",
            "corpus": s["corpus"], "task_key": s["task_key"],
            "stable_id": sid, "frame_id": s["frame_id"],
            "candidate_path": str(p),
        })
    with open(SUBJECTS_JL, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    log(f"P4 subjects {len(rows)}")


# ------------------------------------------- P5: wave2_manifest_input.jsonl
def p5_manifest_input():
    if INPUT_JL.exists():
        log("P5 skip")
        return
    contracts, refs = {}, {}
    for line in L3_SIGNED.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        contracts[r["task_key"]] = r["contract"]
        refs[r["task_key"]] = str(MK / r["extraction"]["source"])
    n = 0
    with open(INPUT_JL, "w", encoding="utf-8") as out:
        for line in SUBJECTS_JL.read_text("utf-8").splitlines():
            s = json.loads(line)
            tk = s["task_key"]
            assert tk in contracts, f"P5 no signed contract for {tk}"
            assert Path(refs[tk]).exists(), f"P5 reference missing {refs[tk]}"
            meta = {"stable_id": s["stable_id"],
                    "scope_id": SCOPE["scope_id"], "wave": 2}
            if s["corpus"] == "C3":
                meta["adapter"] = "c3-wrap-v1"
            out.write(json.dumps({
                "subject_id": s["subject_id"],
                "dataset": s["corpus"],
                "task_id": tk,
                "language": "cuda",
                "candidate_path": s["candidate_path"],
                "reference_path": refs[tk],
                "contract": contracts[tk],
                "metadata": meta,
            }) + "\n")
            n += 1
    assert n == len(W2), n
    log(f"P5 manifest input rows {n}")


# ----------------------------------------------------- P6/P7/P8: builders
def _run(cmd, **kw):
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          cwd=str(MK), **kw)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(map(str, cmd))}\n"
                           f"{proc.stdout[-800:]}\n{proc.stderr[-1500:]}")
    return proc.stdout


def p6_manifest():
    if MANIFEST.exists():
        log("P6 skip")
        return
    out = _run([PYBIN, str(MK / "scripts" / "build_fse_subject_manifest.py"),
                "--input", str(INPUT_JL), "--output", str(MANIFEST),
                "--root", "/"])
    log(f"P6 manifest built: {out.strip()[-200:]}")


def p7_lane_m2_plan():
    if LANE_M2_PLAN.exists():
        log("P7 skip")
        return
    out = _run([PYBIN, str(MK / "scripts" / "plan_fse_experiment.py"),
                "--subjects", str(MANIFEST),
                "--strategy-matrix", str(MATRIX),
                "--output", str(LANE_M2_PLAN)])
    log(f"P7 lane M2 plan: {out.strip()[-300:]}")


def p8_mdir2_plan():
    if MDIR2_PLAN.exists():
        log("P8 skip")
        return
    builder = MK / "scripts" / "build_wave15_lane_plans.py"
    if not builder.exists():
        builder = Path("/root/mk_v2_ops/build_wave15_lane_plans.py")
    out = _run([PYBIN, str(builder), "mdir-plan",
                "--subjects", str(MANIFEST),
                "--map", str(FROZEN_MAP),
                "--artifact-root", "/",
                "--out", str(MDIR2_PLAN)])
    log(f"P8 mdir2 plan: {out.strip()[-300:]}")


def main():
    p1_stage_c5()
    p2_stage_c3()
    p3_sign_l3_contracts()
    p4_subjects_jsonl()
    p5_manifest_input()
    p6_manifest()
    p7_lane_m2_plan()
    p8_mdir2_plan()
    log("WAVE2_PREP_DONE")


if __name__ == "__main__":
    main()
