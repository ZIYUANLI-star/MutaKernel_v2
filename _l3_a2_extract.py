"""A2: re-extract the C2/C3/C5 contract batch now that level3 is vendored.

CPU-only (CUDA_VISIBLE_DEVICES is cleared), writes to a NEW path so the old
batch stays byte-identical, and then runs the non-negotiable regression gate:
every one of the 200 task_ids already extracted must come back with the same
contract_sha256.  A single mismatch aborts and reports.
"""
import io

import _remote

SCRIPT = r'''
import hashlib, json, subprocess, sys, time
from pathlib import Path

MK = Path("/root/mk_v2")
E2 = Path("/root/mk_v2_runs/e2_reconcile")
OLD = E2 / "contracts_c2c3c5_draft.jsonl"
NEW = E2 / "contracts_c2c3c5_draft_l3.jsonl"
FRAMES = [E2 / ("C%s_collection_frame.jsonl" % n) for n in ("2", "3", "5")]

print("=== A2 contract re-extraction  %s ==="
      % time.strftime("%Y-%m-%dT%H:%M:%S%z"))
old_rows = [json.loads(l) for l in OLD.read_text().splitlines() if l.strip()]
old_digest = {r["task_id"]: r["contract_sha256"] for r in old_rows}
old_batch = hashlib.sha256(OLD.read_bytes()).hexdigest()
print("old batch: %d contracts, batch_sha256=%s" % (len(old_rows), old_batch))
print("level3 files vendored: %d"
      % len(list((MK / "KernelBench/KernelBench/level3").glob("*.py"))))

cmd = ["/root/miniconda3/bin/python", "scripts/extract_contracts.py",
       "--kernelbench-root", "KernelBench", "--frames"] \
      + [str(f) for f in FRAMES] + ["--out", str(NEW)]
print("\ncommand: %s" % " ".join(cmd))
started = time.time()
result = subprocess.run(cmd, cwd=str(MK), capture_output=True, text=True,
                        timeout=5400,
                        env={"PATH": "/root/miniconda3/bin:/usr/bin:/bin",
                             "CUDA_VISIBLE_DEVICES": "",
                             "HOME": "/root"})
elapsed = time.time() - started
lines = (result.stdout + result.stderr).splitlines()
failed = [l for l in lines if "FAILED" in l]
print("exit=%d elapsed=%.1fs stdout_lines=%d" % (result.returncode, elapsed,
                                                 len(lines)))
print("tail:")
for line in lines[-14:]:
    print("  ", line[:190])
if failed:
    print("\nextractor FAILED lines (%d):" % len(failed))
    for line in failed:
        print("  ", line[:190])

if result.returncode != 0:
    print("A2_EXTRACT_FAILED")
    raise SystemExit(1)

new_rows = [json.loads(l) for l in NEW.read_text().splitlines() if l.strip()]
new_digest = {r["task_id"]: r["contract_sha256"] for r in new_rows}
new_batch = hashlib.sha256(NEW.read_bytes()).hexdigest()
freeze = json.loads(NEW.with_suffix(".freeze.json").read_text())
print("\n=== new batch ===")
print("contracts=%d failures=%d batch_sha256=%s"
      % (freeze["contracts"], len(freeze["failures"]), freeze["batch_sha256"]))
print("file sha256 recomputed: %s (matches freeze: %s)"
      % (new_batch, new_batch == freeze["batch_sha256"]))
levels = {}
for t in new_digest:
    levels[t.split("_")[0]] = levels.get(t.split("_")[0], 0) + 1
print("by level:", dict(sorted(levels.items())))

print("\n=== regression gate: the 200 pre-existing contract_sha256 ===")
missing = sorted(t for t in old_digest if t not in new_digest)
changed = sorted(t for t in old_digest
                 if t in new_digest and old_digest[t] != new_digest[t])
print("pre-existing task_ids: %d ; missing from the new batch: %d ; "
      "changed digest: %d" % (len(old_digest), len(missing), len(changed)))
for t in missing[:10]:
    print("   MISSING %s" % t)
for t in changed[:10]:
    print("   CHANGED %s: %s -> %s" % (t, old_digest[t][:16], new_digest[t][:16]))

added = sorted(t for t in new_digest if t not in old_digest)
print("newly extracted task_ids: %d" % len(added))
print("   %s" % ", ".join(added[:8]))

if freeze["failures"]:
    print("\n=== extraction failures, by reason ===")
    kinds = {}
    for row in freeze["failures"]:
        kinds.setdefault(row.get("error", "?")[:90], []).append(row.get("task_id"))
    for reason, ids in sorted(kinds.items()):
        print("   %-92s n=%d" % (reason, len(ids)))
        print("      %s" % ", ".join(sorted(ids)[:12]))

report = {
    "step": "A2 re-extract C2/C3/C5 contracts with level3 vendored",
    "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "elapsed_s": round(elapsed, 1),
    "old_path": str(OLD), "old_contracts": len(old_rows),
    "old_batch_sha256": old_batch,
    "new_path": str(NEW), "new_contracts": freeze["contracts"],
    "new_batch_sha256": freeze["batch_sha256"],
    "failures": freeze["failures"],
    "regression_missing": missing, "regression_changed": changed,
    "newly_extracted": added,
    "regression_pass": not missing and not changed,
}
Path("/root/_l3_a2_report.json").write_text(json.dumps(report, indent=2,
                                                       sort_keys=True))
print("\nwrote /root/_l3_a2_report.json")
print("A2_%s" % ("REGRESSION_PASS" if report["regression_pass"]
                 else "REGRESSION_FAIL"))
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_l3_a2_extract.py")
sftp.close()
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python "
               "/root/_l3_a2_extract.py", timeout=5700)
c.close()
