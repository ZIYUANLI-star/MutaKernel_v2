"""Package the 464 wave-1 C5 subjects (matched by raw_sha256) for upload.

Frame origins omit the top-level split dir (baseline_eval/repeated_sampling),
so files are resolved by content hash: raw_sha256 = sha256 of the kernel
source text (verified below).  Output: external_benchmarks staging dir +
registry + tar.gz.
"""
import hashlib
import json
import tarfile
from pathlib import Path

SCOPE = Path(r"MutakernelV2\实验\补充实验数据\e3_campaign_scope_v1.json")
RAW = Path(r"external\C5_kernelbench_samples")
STAGE = Path(r"_e3_stage\c5_wave1")

scope = json.loads(SCOPE.read_text(encoding="utf-8"))
targets = {s["stable_id"]: s for s in scope["wave1_subjects"]
           if s["corpus"] == "C5"}
print("wave-1 C5 subjects wanted:", len(targets))

# frame rows give raw_sha256 per stable_id
frame = {}
fp = Path(r"MutakernelV2\实验\补充实验数据\collection_frames\C5_collection_frame.jsonl")
for line in open(fp, encoding="utf-8"):
    r = json.loads(line)
    frame[r["stable_id"]] = r
want_by_raw = {}
for sid, s in targets.items():
    want_by_raw[frame[sid]["raw_sha256"]] = s

# scan all kernel.json files; hash candidates: kernel text, full file bytes
found = {}
scanned = 0
hash_mode_counts = {"kernel_text": 0, "file_bytes": 0}
for p in RAW.rglob("kernel.json"):
    scanned += 1
    raw = p.read_bytes()
    h_file = hashlib.sha256(raw).hexdigest()
    mode = None
    if h_file in want_by_raw:
        mode = "file_bytes"
    else:
        try:
            d = json.loads(raw.decode("utf-8"))
            k = d.get("kernel")
            if isinstance(k, str):
                h_k = hashlib.sha256(k.encode("utf-8")).hexdigest()
                if h_k in want_by_raw:
                    mode = "kernel_text"
                    h_file = h_k
        except Exception:
            continue
    if mode and h_file in want_by_raw and h_file not in found:
        found[h_file] = p
        hash_mode_counts[mode] += 1

print("scanned kernel.json files:", scanned)
print("matched:", len(found), "of", len(want_by_raw), hash_mode_counts)
missing = [want_by_raw[h]["stable_id"][:16] for h in want_by_raw
           if h not in found]
if missing:
    print("MISSING (first 10):", missing[:10])
    raise SystemExit("cannot package: %d missing" % len(missing))

STAGE.mkdir(parents=True, exist_ok=True)
registry = []
for h, p in found.items():
    s = want_by_raw[h]
    sid16 = s["stable_id"][:16]
    dest = STAGE / sid16
    dest.mkdir(exist_ok=True)
    (dest / "kernel.json").write_bytes(p.read_bytes())
    registry.append({
        "stable_id": s["stable_id"], "task_key": s["task_key"],
        "frame_id": s["frame_id"], "raw_sha256": h,
        "source_path": str(p.relative_to(RAW)),
    })
registry.sort(key=lambda r: (r["task_key"], r["stable_id"]))
(STAGE / "registry.json").write_text(
    json.dumps({"scope_id": scope["scope_id"], "corpus": "C5",
                "subjects": registry}, indent=1), encoding="utf-8")

tar_path = Path("_e3_stage/c5_wave1.tar.gz")
with tarfile.open(tar_path, "w:gz") as tf:
    tf.add(STAGE, arcname="c5_wave1")
print("staged:", len(registry), "->", tar_path,
      "%.1f MB" % (tar_path.stat().st_size / 1e6))
print("C5_PACKAGE_DONE")
