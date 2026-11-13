#!/usr/bin/env python3
"""Execute the prespecified human-calibration decision rules on frozen data.

Consumes the locked annotation record (instrument 1 vetoed units, instrument 2
search records) plus the same frozen ledgers as ``aggregate_fse_v4.py``, and
emits:

  (a) the post-veto recomputation of the headline pools and gaps
      (decision rule (a) of the study protocol / manuscript section 5.8);
  (b) the family veto asymmetry with exact Fisher p (decision rule (b));
  (c) the all-PASS-frame decomposition of instrument 2's findings
      (inside/outside the heterogeneous union W) and the search-conditional
      defect-population estimate used for Rec-hat.

All numbers are written to ``_final_outputs/human_calibration_v1.json`` with
source-file hashes.
"""

from __future__ import annotations

import csv
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from aggregate_fse_v4 import (  # noqa: E402
    OUR_STRATEGIES,
    by_corpus,
    corpus,
    load_contracts,
    read_jsonl,
    repair_detection_sets,
    scan_b11,
    scan_ports,
    strategy_rows,
    strict_rows,
    task,
    task_cluster_bootstrap_ci,
    task_signflip_p,
)
from aggregate_fse_v4 import fail_set, streak_detection_sets  # noqa: E402
from src.experiments.manifest import sha256_file, stable_json_sha256  # noqa: E402

DATA = Path(r"D:\mk_ex")
FETCHED = PROJECT_ROOT / "tmp" / "minimal_repair_inputs"
REPAIR_CAMPAIGN = PROJECT_ROOT / "tmp" / "remote_results" / "minimal_repair_20260826"
STREAK_CAMPAIGN = (
    PROJECT_ROOT / "tmp" / "remote_results" / "timeout_streak_repair_20260827"
)
P3 = PROJECT_ROOT / "tmp" / "lane_p3_evidence"
ANNOT = PROJECT_ROOT / "MutakernelV2" / "人工标注"
OUTPUT = PROJECT_ROOT / "_final_outputs" / "human_calibration_v1.json"

SEED = 20260819
BOOT_N = 10_000


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def level(subject_id: str) -> str:
    task_id = task(subject_id)
    return "_".join(task_id.split("_")[:2])


def stratum(subject_id: str) -> str:
    return f"{corpus(subject_id)}__cuda__{level(subject_id)}"


def fisher_two_sided(a: int, b: int, c: int, d: int) -> float:
    r1, r2, c1 = a + b, c + d, a + c
    n = r1 + r2

    def pmf(x: int) -> float:
        return math.comb(r1, x) * math.comb(r2, c1 - x) / math.comb(n, c1)

    lo, hi = max(0, c1 - r2), min(r1, c1)
    p_obs = pmf(a)
    return min(1.0, sum(pmf(x) for x in range(lo, hi + 1) if pmf(x) <= p_obs * (1 + 1e-9)))


def diff_bootstrap_ci(left: set, right: set, pool: set, rounds: int = BOOT_N):
    subjects_by_task: dict[str, list[str]] = defaultdict(list)
    for subject in pool:
        subjects_by_task[task(subject)].append(subject)
    tasks = sorted(subjects_by_task)
    rng = random.Random(SEED)
    estimates = []
    for _ in range(rounds):
        sampled = [rng.choice(tasks) for _ in tasks]
        den = sum(len(subjects_by_task[item]) for item in sampled)
        num_left = sum(
            sum(subject in left for subject in subjects_by_task[item]) for item in sampled
        )
        num_right = sum(
            sum(subject in right for subject in subjects_by_task[item]) for item in sampled
        )
        estimates.append(100.0 * (num_left - num_right) / den)
    estimates.sort()
    return (estimates[int(0.025 * rounds)], estimates[min(rounds - 1, int(0.975 * rounds))])


def main() -> None:
    manifests = [
        DATA / "cardc/e3_campaign/wave1_subject_manifest_v2.json",
        DATA / "cardc/e3_campaign/wave2_subject_manifest.json",
        FETCHED / "b/wave3_subject_manifest.json",
    ]
    contracts, meta = load_contracts(manifests)
    subjects = set(meta)
    md_paths = [
        DATA / "root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl",
        DATA / "cardc/e3_campaign/wave15/lane_d_run/observations.jsonl",
        DATA / "w23/wave2/lane_m2_run/observations.jsonl",
        DATA / "w23/wave2/lane_d2_run/observations.jsonl",
        DATA / "w23/wave3/lane_m3_run/observations.jsonl",
        DATA / "w23/wave3/lane_d3_run/observations.jsonl",
    ]
    md_all = read_jsonl(md_paths)
    md = {
        key: row
        for key, row in md_all.items()
        if row.get("strategy_name") in OUR_STRATEGIES
    }
    md_strict = strict_rows(md, contracts)

    rows: dict[str, set] = {}
    for strategy_name, display in OUR_STRATEGIES.items():
        rows[display] = fail_set(strategy_rows(md_strict, strategy_name))
    repair_sets = repair_detection_sets(REPAIR_CAMPAIGN)
    rows["M-full"] |= repair_sets.get("M-full", set())
    rows["M-dir"] |= repair_sets.get("M-dir", set())
    for display, detected in streak_detection_sets(STREAK_CAMPAIGN).items():
        rows[display] |= detected
    rows["Dtype-8"] = set(rows["M-ctx"])

    port_dirs = {
        "B7": [
            DATA / "cardc/e3_campaign/wave15/lane_p_b7",
            DATA / "cardc/e3_campaign/wave2/lane_p2_b7",
            P3 / "lane_p3_b7",
        ],
        "B8": [
            DATA / "cardc/e3_campaign/wave15/lane_p_b8",
            DATA / "cardc/e3_campaign/wave2/lane_p2_b8",
            P3 / "lane_p3_b8",
        ],
        "B9": [
            DATA / "cardc/e3_campaign/wave15/lane_p_b9",
            DATA / "cardc/e3_campaign/wave2/lane_p2_b9",
            P3 / "lane_p3_b9",
        ],
    }
    for name, directories in port_dirs.items():
        rows[name] = scan_ports(directories, name.lower())
    rows["B11"] = scan_b11(
        [
            DATA / "b11_w15/wave15/lane_p_b11",
            DATA / "cardc/e3_campaign/wave2/lane_p2_b11",
            P3 / "lane_p3_b11",
        ]
    )

    layer_a = set().union(
        *(rows[name] for name in ("B1u", "B3", "B4", "B5", "M-ctx", "M-full", "M-dir"))
    )
    layer_b_union = rows["B7"] | rows["B8"] | rows["B9"] | rows["B11"]
    union = layer_a | layer_b_union
    layer_b_only = union - layer_a
    w_ext = {subject for subject in union if corpus(subject) in {"C3", "C5"}}
    assert len(layer_a) == 692 and len(union) == 780 and len(w_ext) == 735, (
        len(layer_a),
        len(union),
        len(w_ext),
    )

    anchor_raw = read_jsonl(md_paths, {"five-iid-historical-anchor"})
    accepted = subjects - fail_set(anchor_raw.values())
    assert len(accepted) == 661, len(accepted)

    # ---- instrument-2 sampling frame: zero any-mode FAIL in the six M/D ledgers.
    frame = subjects - fail_set(md_all.values())
    frame_by_stratum: dict[str, int] = defaultdict(int)
    for subject in frame:
        frame_by_stratum[stratum(subject)] += 1
    stats2 = json.loads(
        (ANNOT / "仪器2_全PASS人工搜索_Table12" / "抽样框统计_instrument2.json").read_text(
            encoding="utf-8"
        )
    )
    frame_matches = len(frame) == stats2["population"] and all(
        frame_by_stratum.get(name, 0) == value["population"]
        for name, value in stats2["strata"].items()
    )

    residual_union = frame - union
    frame_layer_a = frame & layer_a

    # ---- instrument-2 findings from the locked search records.
    sample2 = read_csv(ANNOT / "仪器2_全PASS人工搜索_Table12" / "受试抽样清单_instrument2.csv")
    calib_ids = {
        row["item_id"]
        for row in read_csv(
            ANNOT / "仪器2_全PASS人工搜索_Table12" / "校准题答案_仅协调人.csv"
        )
    }
    rec_a = {
        row["item_id"]: row
        for row in read_csv(ANNOT / "仪器2_全PASS人工搜索_Table12" / "搜索记录表_A.csv")
    }
    rec_b = {
        row["item_id"]: row
        for row in read_csv(ANNOT / "仪器2_全PASS人工搜索_Table12" / "搜索记录表_B.csv")
    }

    def found(record: dict | None) -> bool:
        return bool(
            record
            and record.get("defect_found", "").strip().lower() == "yes"
            and record.get("witness_replay_verified", "").strip().lower() == "yes"
        )

    real_items = [row for row in sample2 if row["item_id"] not in calib_ids]
    found_subjects = set()
    per_stratum = defaultdict(lambda: {"n": 0, "found": 0, "found_in_union": 0, "sampled_in_union": 0})
    for row in real_items:
        item, subject = row["item_id"], row["subject_id"]
        hit = found(rec_a.get(item)) or (
            row["dual_search"] == "yes" and found(rec_b.get(item))
        )
        cell = per_stratum[row["stratum"]]
        cell["n"] += 1
        cell["sampled_in_union"] += int(subject in union)
        if hit:
            found_subjects.add(subject)
            cell["found"] += 1
            cell["found_in_union"] += int(subject in union)

    pops = {name: value["population"] for name, value in stats2["strata"].items()}
    ht_total = sum(
        pops[name] / cell["n"] * cell["found"] for name, cell in per_stratum.items()
    )
    ht_outside = sum(
        pops[name] / cell["n"] * (cell["found"] - cell["found_in_union"])
        for name, cell in per_stratum.items()
    )
    sampled_residual = [
        row for row in real_items if row["subject_id"] in residual_union
    ]
    found_residual = [
        row for row in sampled_residual if row["subject_id"] in found_subjects
    ]

    # ---- instrument-1: vetoed units, exact Fisher, family confirmation.
    vetoed = read_csv(ANNOT / "汇总" / "vetoed_units.csv")
    veto_subjects = {row["subject_id"] for row in vetoed}
    assert all(row["family"] == "external" for row in vetoed)

    table11 = read_csv(ANNOT / "汇总" / "A_B结果对照_Table11.csv")
    analyzed = [row for row in table11 if row["a_label"] != "FLAG_NONREPRO"]
    ours_rows = [row for row in analyzed if row["family"] == "ours"]
    ext_rows = [row for row in analyzed if row["family"] == "external"]
    vo = sum(row["a_label"] != "CONFIRM" for row in ours_rows)
    ve = sum(row["a_label"] != "CONFIRM" for row in ext_rows)
    fisher_p = fisher_two_sided(vo, len(ours_rows) - vo, ve, len(ext_rows) - ve)

    stats1 = json.loads(
        (ANNOT / "仪器1_见证盲审_Table11" / "抽样框统计_instrument1.json").read_text(
            encoding="utf-8"
        )
    )
    pop1 = {k: v["population"] for k, v in stats1.items() if not k.startswith("_")}
    strata_conf = defaultdict(list)
    for row in analyzed:
        strata_conf[row["stratum"]].append(1 if row["a_label"] == "CONFIRM" else 0)

    def weighted(unit_lists: dict) -> float:
        num = den = 0.0
        for name, values in unit_lists.items():
            if values:
                num += pop1[name] * (sum(values) / len(values))
                den += pop1[name]
        return num / den if den else float("nan")

    ext_lists = {k: v for k, v in strata_conf.items() if k.endswith("external")}
    rng = random.Random(20260901)
    ext_boot = []
    for _ in range(BOOT_N):
        resampled = {k: [rng.choice(v) for _ in v] for k, v in ext_lists.items()}
        ext_boot.append(weighted(resampled))
    ext_boot.sort()
    ext_conf = weighted(ext_lists)
    ext_ci = (ext_boot[int(0.025 * BOOT_N)], ext_boot[int(0.975 * BOOT_N)])

    # ---- decision rule (a): post-veto recomputation.
    rows_pv = {name: set(detected) for name, detected in rows.items()}
    for name in ("B7", "B8", "B9", "B11"):
        rows_pv[name] -= veto_subjects
    layer_b_union_pv = rows_pv["B7"] | rows_pv["B8"] | rows_pv["B9"] | rows_pv["B11"]
    union_pv = layer_a | layer_b_union_pv
    layer_b_only_pv = union_pv - layer_a
    w_ext_pv = {subject for subject in union_pv if corpus(subject) in {"C3", "C5"}}

    table3_pv = {}
    for corpus_name in ("C2", "C3", "C5", "Total"):
        scope = (
            subjects
            if corpus_name == "Total"
            else {subject for subject in subjects if corpus(subject) == corpus_name}
        )
        accepted_scope = accepted & scope
        table3_pv[corpus_name] = {
            "accepted": len(accepted_scope),
            "layer_a": len(accepted_scope & layer_a),
            "layer_b_only": len(accepted_scope & layer_b_only_pv),
            "union": len(accepted_scope & union_pv),
            "union_rate_pct": 100.0 * len(accepted_scope & union_pv) / len(accepted_scope),
        }

    def record(name: str) -> dict:
        detected = rows_pv[name]
        return {
            "detected_in_pool": len(detected & w_ext_pv),
            "coverage_pct": 100.0 * len(detected & w_ext_pv) / len(w_ext_pv),
            "ci95": list(task_cluster_bootstrap_ci(detected, w_ext_pv)),
        }

    key_rows = ("B1u", "B3", "B4", "B5", "Dtype-8", "M-ctx", "B7", "B8", "B9", "B11", "M-full", "M-dir")
    records_pv = {name: record(name) for name in key_rows}
    gaps = {}
    for name in ("M-full", "M-ctx"):
        delta = records_pv[name]["coverage_pct"] - records_pv["B9"]["coverage_pct"]
        gaps[f"{name}_vs_B9"] = {
            "delta_pp": delta,
            "delta_ci95": list(diff_bootstrap_ci(rows_pv[name], rows_pv["B9"], w_ext_pv)),
            "signflip_p": task_signflip_p(rows_pv[name], rows_pv["B9"], w_ext_pv),
        }

    # Descriptive RQ2 statistics on the raw (pre-veto) pool.
    raw_gaps = {}
    for name in ("M-full", "M-ctx"):
        detected = rows[name] & w_ext
        b9 = rows["B9"] & w_ext
        raw_gaps[f"{name}_vs_B9"] = {
            "delta_pp": 100.0 * (len(detected) - len(b9)) / len(w_ext),
            "delta_ci95": list(diff_bootstrap_ci(rows[name], rows["B9"], w_ext)),
            "signflip_p": task_signflip_p(rows[name], rows["B9"], w_ext),
            "discordant_row_only": len(detected - b9),
            "discordant_b9_only": len(b9 - detected),
        }
    mfull_misses = w_ext - rows["M-full"]
    raw_gaps["complementarity"] = {
        "M-full_misses_on_W_ext": len(mfull_misses),
        "of_which_B9_catches": len(mfull_misses & rows["B9"]),
        "union_M-full_and_B9": len((rows["M-full"] | rows["B9"]) & w_ext),
        "union_pct": 100.0 * len((rows["M-full"] | rows["B9"]) & w_ext) / len(w_ext),
    }

    e_pool = {subject for subject in layer_b_union if corpus(subject) in {"C3", "C5"}}
    e_pool_pv = {subject for subject in layer_b_union_pv if corpus(subject) in {"C3", "C5"}}
    e_stats = {
        "E_n": len(e_pool),
        "E_postveto_n": len(e_pool_pv),
        "M-full_cov_pct": 100.0 * len(rows_pv["M-full"] & e_pool_pv) / len(e_pool_pv),
        "M-ctx_cov_pct": 100.0 * len(rows_pv["M-ctx"] & e_pool_pv) / len(e_pool_pv),
        "B9_cov_pct": 100.0 * len(rows_pv["B9"] & e_pool_pv) / len(e_pool_pv),
        "signflip_p_mfull_vs_b9": task_signflip_p(
            rows_pv["M-full"], rows_pv["B9"], e_pool_pv
        ),
    }

    # ---- search-conditional defect-population estimate.
    n_hat = len(layer_a) + ht_total
    n_low = len(layer_a) + len(found_subjects)
    n_high = len(layer_a) + 88  # exact hypergeometric 95% upper bound from instrument 2
    extended_only = len(subjects) - len(frame) - len(layer_a - frame)
    rec_hat = {
        name: {
            "detections_full": len(rows[name]),
            "rec_hat_pct": 100.0 * len(rows[name]) / n_hat,
            "rec_hat_range_pct": [
                100.0 * len(rows[name]) / n_high,
                100.0 * len(rows[name]) / n_low,
            ],
        }
        for name in ("M-full", "M-dir", "M-ctx", "Dtype-8", "B9")
    }

    annotation_sources = [
        ANNOT / "汇总" / "A_B结果对照_Table11.csv",
        ANNOT / "汇总" / "A_B结果对照_Table12.csv",
        ANNOT / "汇总" / "待裁决分歧.csv",
        ANNOT / "汇总" / "vetoed_units.csv",
        ANNOT / "汇总" / "仪器1_结果.json",
        ANNOT / "汇总" / "仪器2_结果.json",
        ANNOT / "仪器1_见证盲审_Table11" / "抽样清单_instrument1.csv",
        ANNOT / "仪器1_见证盲审_Table11" / "标注表_A.csv",
        ANNOT / "仪器1_见证盲审_Table11" / "标注表_B.csv",
        ANNOT / "仪器2_全PASS人工搜索_Table12" / "受试抽样清单_instrument2.csv",
        ANNOT / "仪器2_全PASS人工搜索_Table12" / "搜索记录表_A.csv",
        ANNOT / "仪器2_全PASS人工搜索_Table12" / "搜索记录表_B.csv",
        ANNOT / "仪器2_全PASS人工搜索_Table12" / "校准题答案_仅协调人.csv",
    ]
    result = {
        "schema_version": "1.0",
        "frame_check": {
            "frame_size": len(frame),
            "matches_frozen_stats": frame_matches,
            "frame_in_layer_a": sorted(frame_layer_a),
            "residual_union_screen": {
                "size": len(residual_union),
                "by_corpus": by_corpus(residual_union),
                "sampled": len(sampled_residual),
                "human_found": len(found_residual),
            },
        },
        "instrument2_decomposition": {
            "found_total": len(found_subjects),
            "found_in_union_W": sum(
                cell["found_in_union"] for cell in per_stratum.values()
            ),
            "found_outside_union_W": len(found_subjects)
            - sum(cell["found_in_union"] for cell in per_stratum.values()),
            "per_stratum": {name: dict(cell) for name, cell in sorted(per_stratum.items())},
            "HT_total": ht_total,
            "HT_outside_union_W": ht_outside,
        },
        "instrument1_families": {
            "fisher_p_exact": fisher_p,
            "ours_confirm_analyzed": f"{len(ours_rows) - vo}/{len(ours_rows)}",
            "external_confirm_analyzed": f"{len(ext_rows) - ve}/{len(ext_rows)}",
            "external_weighted_confirmation": ext_conf,
            "external_weighted_ci95": list(ext_ci),
        },
        "postveto": {
            "vetoed_units": len(vetoed),
            "vetoed_subjects_in_layer_b_only": len(veto_subjects & layer_b_only),
            "vetoed_subjects_with_layer_a": len(veto_subjects & layer_a),
            "pools": {
                "union": len(union_pv),
                "layer_b_only": len(layer_b_only_pv),
                "W_ext": len(w_ext_pv),
                "E_pool": e_stats,
            },
            "table3": table3_pv,
            "rows_on_W_ext": records_pv,
            "gaps": gaps,
        },
        "raw_pool_gaps": raw_gaps,
        "search_conditional": {
            "layer_a": len(layer_a),
            "HT_defects_in_frame": ht_total,
            "N_hat": n_hat,
            "N_range": [n_low, n_high],
            "extended_only_unsearched": extended_only,
            "layer_b_only_outside_frame": len(layer_b_only - frame),
            "rec_hat": rec_hat,
        },
        "annotation_source_files": [
            {"path": str(path), "sha256": sha256_file(path)}
            for path in annotation_sources
        ],
    }
    result["result_sha256"] = stable_json_sha256(result)
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=1),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=1)[:6000])
    print("written", OUTPUT)


if __name__ == "__main__":
    main()
