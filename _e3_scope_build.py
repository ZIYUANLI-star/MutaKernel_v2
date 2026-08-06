"""Build the frozen E3 campaign scope manifest (C2 deferred by user decision).

Wave 1 = C3 + C5 subjects referencing KernelBench L1/L2 tasks (contracts
drafted for these 200 tasks; B9 calibration covers their (task,dtype) units).
Wave 2 (deferred) = L3-referencing subjects (await L3 contract review +
L3 calibration batch).  C2 (CUDA-L1) deferred per user decision 2026-08-01.
C4 awaits human-written references.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

BASE = Path(r"MutakernelV2\实验\补充实验数据\collection_frames")
OUT = Path(r"MutakernelV2\实验\补充实验数据\e3_campaign_scope_v1.json")


def load(name):
    return [json.loads(l) for l in
            open(BASE / name, encoding="utf-8") if l.strip()]


def level_of(task_key):
    # task_key like KB_L1_P23
    return task_key.split("_")[1]


c3 = load("C3_subject_frame.jsonl")
c5 = load("C5_collection_frame.jsonl")

c3_subjects = [{"corpus": "C3", "stable_id": r["stable_id"],
                "task_key": r["task_key"], "frame_id": r["frame_id"]}
               for r in c3]

c5_eligible = [r for r in c5 if r["included"] and r["accepted"]
               and not r["duplicate_within_corpus"]]
c5_subjects = [{"corpus": "C5", "stable_id": r["stable_id"],
                "task_key": r["task_key"], "frame_id": r["frame_id"]}
               for r in c5_eligible]

print("C3 subjects:", len(c3_subjects),
      "levels:", dict(Counter(level_of(s["task_key"]) for s in c3_subjects)))
print("C5 eligible:", len(c5_subjects),
      "levels:", dict(Counter(level_of(s["task_key"]) for s in c5_subjects)))

wave1 = [s for s in c3_subjects + c5_subjects
         if level_of(s["task_key"]) in ("L1", "L2")]
wave2 = [s for s in c3_subjects + c5_subjects
         if level_of(s["task_key"]) == "L3"]
wave1.sort(key=lambda s: (s["corpus"], s["task_key"], s["stable_id"]))
wave2.sort(key=lambda s: (s["corpus"], s["task_key"], s["stable_id"]))

print("wave1 (L1+L2):", len(wave1),
      dict(Counter(s["corpus"] for s in wave1)))
print("wave2 (L3, deferred):", len(wave2),
      dict(Counter(s["corpus"] for s in wave2)))

manifest = {
    "scope_id": "e3_campaign_scope_v1",
    "created_at": "2026-08-01T17:15+08:00",
    "decision": {
        "c2_cuda_l1": "DEFERRED by user decision 2026-08-01 (85 subjects; "
                      "Table 6a CUDA-L1 row reported later or marked deferred)",
        "c4_tritonbench_g": "awaits 60 human-written references "
                            "(prereg subsample)",
        "wave1": "C3+C5 subjects on KB L1/L2 tasks",
        "wave2": "C3+C5 subjects on KB L3 tasks; await L3 contract review + "
                 "L3 B9 calibration batch",
    },
    "eligibility_rule": {
        "C3": "all 227 representative subjects (subject frame, "
              "min_stable_id_over_accepted_included)",
        "C5": "included AND accepted AND NOT duplicate_within_corpus",
    },
    "counts": {
        "wave1_total": len(wave1),
        "wave1_by_corpus": dict(Counter(s["corpus"] for s in wave1)),
        "wave2_total": len(wave2),
        "wave2_by_corpus": dict(Counter(s["corpus"] for s in wave2)),
    },
    "wave1_subjects": wave1,
    "wave2_subjects": wave2,
}
blob = json.dumps(manifest, indent=1, ensure_ascii=False)
digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
manifest["self_note"] = "sha256 over content excluding this field"
OUT.write_text(blob, encoding="utf-8")
print("manifest written:", OUT)
print("sha256:", digest)
