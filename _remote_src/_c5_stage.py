
import hashlib, json
from pathlib import Path

def normalize_source(source):
    lines = [l.rstrip() for l in source.replace("\r\n", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"

scope = json.load(open("/root/mk_v2_runs/e3_campaign/e3_campaign_scope_v1.json"))
want = {s["stable_id"]: s for s in scope["wave1_subjects"] if s["corpus"] == "C5"}
print("wave-1 C5 subjects wanted:", len(want))

up = Path("/root/mk_v2/external/C5_kernelbench_samples_wave1")
# find the per-subject dirs (registry.json written at package time)
reg_files = list(up.rglob("registry.json"))
assert reg_files, "no packaged registry found under %s" % up
pkg = json.load(open(reg_files[0]))
by_sid = {r["stable_id"]: r for r in pkg["subjects"]}
root = reg_files[0].parent

dst = Path("/root/mk_v2_runs/e3_corpora/c5_wave1")
cand = dst / "candidates"
cand.mkdir(parents=True, exist_ok=True)

registry, missing, badhash = [], [], []
for sid, s in sorted(want.items(), key=lambda kv: (kv[1]["task_key"], kv[0])):
    r = by_sid.get(sid)
    kj = root / sid[:16] / "kernel.json" if r else None
    if kj is None or not kj.exists():
        missing.append(sid[:16]); continue
    d = json.loads(kj.read_text(encoding="utf-8"))
    src = d.get("kernel")
    if not isinstance(src, str) or not src.strip():
        missing.append(sid[:16] + ":empty"); continue
    h = hashlib.sha256(normalize_source(src).encode("utf-8")).hexdigest()
    if h != sid:
        badhash.append(sid[:16]); continue
    (cand / (sid + ".py")).write_text(src, encoding="utf-8")
    registry.append({"stable_id": sid, "task_key": s["task_key"],
                     "frame_id": s["frame_id"], "sha256_normalized": h})

(dst / "registry.json").write_text(json.dumps({
    "scope_id": scope["scope_id"], "corpus": "C5",
    "source": "uploaded c5_wave1 package (raw_sha256-verified at upload); "
              "kernel text extracted, normalized hash re-verified == stable_id",
    "subjects": registry}, indent=1), encoding="utf-8")
print("staged:", len(registry), "missing:", missing[:5], "badhash:", badhash[:5])
assert not missing and not badhash, "STAGING INCOMPLETE"
print("C5_STAGE_OK")
