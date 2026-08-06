# -*- coding: utf-8 -*-
"""Finalize E2: install fetched C3 artifacts, merge freeze, cross-corpus dup check."""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.abspath("."))
from scripts.reconcile_corpora import merge_freeze  # noqa: E402
from pathlib import Path

DIR = Path("MutakernelV2") / "实验" / "补充实验数据" / "collection_frames"

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

# 1. install fetched C3 files under canonical names, verify digests
remote_freeze = json.loads((DIR / "_remote_collection_frames.freeze.json").read_text(encoding="utf-8"))
c3 = remote_freeze["corpora"]["C3"]
expected_frame = c3["frame_sha256"]
expected_subject = c3["subject_frame"]["subject_frame_sha256"]

frame_src = DIR / "_remote_C3_collection_frame.jsonl"
subject_src = DIR / "_remote_C3_subject_frame.jsonl"
assert sha(frame_src) == expected_frame, "C3 frame sha mismatch after transfer"
assert sha(subject_src) == expected_subject, "C3 subject frame sha mismatch after transfer"

frame_dst = DIR / "C3_collection_frame.jsonl"
subject_dst = DIR / "C3_subject_frame.jsonl"
if frame_dst.exists():
    frame_dst.unlink()
if subject_dst.exists():
    subject_dst.unlink()
os.rename(frame_src, frame_dst)
os.rename(subject_src, subject_dst)
print("installed C3 frames, digests verified")

# 2. merge C3 entry into the local freeze with repo-relative paths
c3["frame_path"] = str(frame_dst)
c3["subject_frame"]["subject_frame_path"] = str(subject_dst)
c3["reconciled_on"] = "remote (pyarrow); digests verified after transfer"
merge_freeze(DIR / "collection_frames.freeze.json", {"C3": c3})
print("freeze merged")

# 3. cross-corpus duplicate check over all four frames
ids = {}
for corpus in ("C2", "C3", "C4", "C5"):
    s = {}
    with open(DIR / f"{corpus}_collection_frame.jsonl", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            s.setdefault(row["stable_id"], row["frame_id"])
    ids[corpus] = s
    print(corpus, "unique stable_ids:", len(s))

cross = []
corpora = list(ids)
for i, a in enumerate(corpora):
    for b in corpora[i + 1:]:
        inter = set(ids[a]) & set(ids[b])
        cross.append({"pair": f"{a}x{b}", "shared_stable_ids": len(inter),
                      "examples": sorted(inter)[:5]})
        print(f"{a} x {b}: {len(inter)} shared stable_ids")

(DIR / "cross_corpus_duplicates.json").write_text(
    json.dumps({"pairs": cross,
                "note": "byte-normalized stable_id intersections across the "
                        "four frames; duplicates are flagged, never dropped"},
               indent=2), encoding="utf-8")

# 4. clean leftover fetched freeze
(DIR / "_remote_collection_frames.freeze.json").unlink()
print("FINALIZE_DONE")
