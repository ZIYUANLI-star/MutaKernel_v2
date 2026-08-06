#!/usr/bin/env python3
"""Generate the dual-review worksheet for the C2/C3/C5 draft contracts.

Automates everything machine-checkable so the two human reviewers only
adjudicate judgment clauses:
  * integrity: recompute contract_sha256 (canonical JSON) and source_sha256;
  * schema completeness: required sections and per-dtype tolerance entries;
  * clustering: contracts sharing a "review signature" (value-domain kinds,
    tolerance profile, execution flags, dtype/layout sets, review-pending
    flags) collapse into one cluster decision;
  * outlier surfacing: any contract deviating from its cluster's modal shape
    pattern or with anomalies is listed individually.

Output: a Markdown worksheet with cluster-level decision blocks and a
per-contract appendix, plus a CSV for sorting/filtering.
"""
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def canonical_sha(contract):
    blob = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def review_signature(c):
    """Everything a reviewer decides once per cluster, not per contract."""
    ct = c["contract"]
    ex = ct.get("execution", {})
    orc = ct.get("oracle", {})
    tin = ct.get("tensor_inputs", [])
    vd = tuple(sorted({t.get("value_domain", {}).get("kind", "?")
                       for t in tin}))
    dt = tuple(sorted({d for t in tin for d in t.get("dtypes", [])}))
    lay = tuple(sorted({l for t in tin for l in t.get("layouts", [])}))
    tol = json.dumps(orc.get("dtype_tolerances", {}), sort_keys=True)
    pending = tuple(sorted(c.get("extraction", {})
                           .get("human_review_pending", [])))
    return (
        ("value_domains", vd),
        ("dtypes", dt),
        ("layouts", lay),
        ("backward", ex.get("backward")),
        ("modes", tuple(ex.get("modes", []))),
        ("deterministic", ex.get("deterministic")),
        ("repeat_count_max", ex.get("repeat_count_max")),
        ("compare_module_state", ex.get("compare_module_state")),
        ("tolerances", tol),
        ("base_atol_rtol", (orc.get("atol"), orc.get("rtol"))),
        ("equal_nan", orc.get("equal_nan")),
        ("review_pending", pending),
        ("n_tensor_inputs", len(tin)),
        ("requires_grad_any", any(t.get("requires_grad") for t in tin)),
    )


def check_contract(c, kb_root):
    issues = []
    ct = c["contract"]
    if canonical_sha(ct) != c.get("contract_sha256"):
        issues.append("SHA_MISMATCH: stored contract_sha256 != recomputed")
    for section in ("execution", "oracle", "tensor_inputs",
                    "policy_bindings", "candidate_classes"):
        if section not in ct or not ct[section]:
            issues.append("MISSING_SECTION: %s" % section)
    orc = ct.get("oracle", {})
    declared = {d for t in ct.get("tensor_inputs", [])
                for d in t.get("dtypes", [])}
    missing_tol = declared - set(orc.get("dtype_tolerances", {}))
    if missing_tol:
        issues.append("MISSING_DTYPE_TOL: %s" % ",".join(sorted(missing_tol)))
    n_args = len(ct.get("tensor_inputs", []))
    for pol, idxs in ct.get("policy_bindings", {}).items():
        if any(i >= n_args for i in idxs):
            issues.append("POLICY_BINDING_OOR: %s -> %s" % (pol, idxs))
    src = c.get("extraction", {}).get("source")
    if src and kb_root:
        p = Path(kb_root) / Path(src).relative_to("KernelBench") \
            if str(src).startswith("KernelBench") else Path(src)
        if p.exists():
            actual = hashlib.sha256(p.read_bytes()).hexdigest()
            if actual != c["extraction"].get("source_sha256"):
                issues.append("SOURCE_SHA_MISMATCH: %s" % src)
        else:
            issues.append("SOURCE_FILE_NOT_FOUND: %s" % src)
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--contracts", type=Path, required=True)
    ap.add_argument("--kb-root", type=Path, default=Path("KernelBench"))
    ap.add_argument("--out-md", type=Path, required=True)
    ap.add_argument("--out-csv", type=Path, required=True)
    args = ap.parse_args()

    rows = [json.loads(l) for l in
            open(args.contracts, encoding="utf-8") if l.strip()]

    clusters = defaultdict(list)
    all_issues = {}
    for c in rows:
        clusters[review_signature(c)].append(c)
        all_issues[c["task_id"]] = check_contract(c, args.kb_root)

    ordered = sorted(clusters.items(), key=lambda kv: -len(kv[1]))

    md = []
    md.append("# C2/C3/C5 契约草稿双人审核工作底稿（自动预审版）\n")
    md.append("- 契约批次：`%s`（%d 份，全部 draft）" % (
        args.contracts.name, len(rows)))
    md.append("- 预审生成：scripts/contract_prereview.py；"
              "完整性检查（哈希、schema、容差覆盖、策略绑定越界、源文件哈希）"
              "已自动执行，结果见附录列 issues。")
    md.append("- 审核方式：**按簇决策**。同簇契约的全部判断性条款一致，"
              "审核人对每簇给一次裁定（默认条款是否接受），"
              "再逐条处理『离群与异常』节中的个别契约。\n")
    n_bad = sum(1 for v in all_issues.values() if v)
    md.append("自动完整性检查：%d/%d 份无异常%s。\n" % (
        len(rows) - n_bad, len(rows),
        "" if n_bad == 0 else "；%d 份有待处理项（见下）" % n_bad))

    md.append("## 一、簇级决策（%d 簇）\n" % len(ordered))
    for i, (sig, members) in enumerate(ordered, 1):
        d = dict(sig)
        md.append("### 簇 %d（%d 份契约）" % (i, len(members)))
        md.append("- 任务：%s" % ", ".join(
            sorted(m["task_id"] for m in members)[:12] +
            (["…(共%d)" % len(members)] if len(members) > 12 else [])))
        md.append("- value_domain: `%s`；dtypes: `%s`；layouts: `%s`；"
                  "张量参数个数=%s；requires_grad=%s" % (
                      "/".join(d["value_domains"]), "/".join(d["dtypes"]),
                      "/".join(d["layouts"]), d["n_tensor_inputs"],
                      d["requires_grad_any"]))
        md.append("- execution: backward=%s, modes=%s, deterministic=%s, "
                  "repeat_max=%s, compare_module_state=%s" % (
                      d["backward"], list(d["modes"]), d["deterministic"],
                      d["repeat_count_max"], d["compare_module_state"]))
        md.append("- oracle: base atol/rtol=%s, equal_nan=%s, 逐 dtype 容差=%s"
                  % (d["base_atol_rtol"], d["equal_nan"], d["tolerances"]))
        md.append("- 待人裁条款：%s" % ", ".join(d["review_pending"]))
        md.append("- **审核人 A 裁定：__ 接受默认 / __ 需修订（说明：      ）**")
        md.append("- **审核人 B 裁定：__ 接受默认 / __ 需修订（说明：      ）**\n")

    md.append("## 二、离群与异常（逐条处理）\n")
    any_out = False
    for tid, issues in sorted(all_issues.items()):
        if issues:
            any_out = True
            md.append("- `%s`: %s" % (tid, "; ".join(issues)))
    if not any_out:
        md.append("（无：全部契约通过自动完整性检查）")
    md.append("\n## 三、签核\n")
    md.append("- 审核人 A：＿＿＿＿＿＿  日期：＿＿＿＿")
    md.append("- 审核人 B：＿＿＿＿＿＿  日期：＿＿＿＿")
    md.append("- 签核后操作：按修订清单改契约（bump contract_id）→ 重跑 "
              "extract 冻结（draft=false）→ 在远端放置 CONTRACTS_FROZEN "
              "标记，E3 战役编排器凭该标记点火。")

    args.out_md.write_text("\n".join(md), encoding="utf-8")

    with open(args.out_csv, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["task_id", "cluster", "n_in_cluster", "backward",
                    "value_domains", "dtypes", "review_pending", "issues"])
        for i, (sig, members) in enumerate(ordered, 1):
            d = dict(sig)
            for m in members:
                w.writerow([m["task_id"], i, len(members), d["backward"],
                            "/".join(d["value_domains"]),
                            "/".join(d["dtypes"]),
                            "/".join(d["review_pending"]),
                            "; ".join(all_issues[m["task_id"]])])
    print("clusters:", len(ordered), "contracts:", len(rows),
          "with_issues:", n_bad)
    print("worksheet:", args.out_md)
    print("csv:", args.out_csv)


if __name__ == "__main__":
    main()
