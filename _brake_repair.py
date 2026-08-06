"""Undo the earlier adoption: restore the audit owner's marker text verbatim.

The first version of the brake protocol adopted the foreign
PAUSED_FOR_SIGNOFF_RERUN (placed by the audit owner at 21:45:48) and rewrote its
text with its own.  The brake stayed in force throughout -- the file never
disappeared -- so nothing unsafe happened, but the file is another party's and
must read exactly as they wrote it.  The original text was preserved inside the
adopted marker, so it can be restored byte-for-byte.
"""
import io

import _remote

SCRIPT = r'''
import hashlib, json, sys, time
from pathlib import Path
sys.path.insert(0, "/root/mk_v2")
import _b9_brake as B

OUT = Path("/root/mk_v2_runs/e3_b9_calib")
derived = B.derived_path()
marker = B.brake_dir() / (B.PREFIX + B.LEGACY_OWNER)
state = B.brake_dir() / ".derived_state.json"

print("=== brake repair  %s ===" % time.strftime("%Y-%m-%dT%H:%M:%S%z"))
print("derived present :", derived.is_file())
print("adopted marker  :", marker.is_file())
print("state sidecar   :", state.is_file())

if not marker.is_file():
    print("nothing to repair")
    raise SystemExit(0)

record = json.loads(marker.read_text(encoding="utf-8"))
original = record.get("original_text")
if not original:
    sys.exit("REFUSING: the adopted marker has no original_text to restore")

print("\noriginal text to restore (%d bytes):" % len(original))
for line in original.splitlines():
    print("   ", line[:150])
print("\ncurrent file text (%d bytes):" % derived.stat().st_size)
for line in derived.read_text(encoding="utf-8", errors="replace").splitlines():
    print("   ", line[:150])

# restore, then drop our claim.  Order matters: the brake must never be absent.
derived.write_text(original, encoding="utf-8")
state.unlink(missing_ok=True)
archive = B.brake_dir() / "released"
archive.mkdir(parents=True, exist_ok=True)
marker.replace(archive / ("%s%s.adoption_undone_%s"
                          % (B.PREFIX, B.LEGACY_OWNER,
                             time.strftime("%Y%m%dT%H%M%S"))))
print("\nrestored, claim dropped, adoption record archived")

print("\n=== verification ===")
now = derived.read_text(encoding="utf-8")
print("brake still present      :", derived.is_file())
print("text identical to original:", now == original)
print("sha256                   :", hashlib.sha256(now.encode()).hexdigest()[:16])
print("we no longer claim it    :", B.foreign_brake() is not None)
current, foreign = B.sync()
print("sync -> foreign=%r holders=%s" % (foreign, [o for o, _ in current]))
print("text unchanged by sync   :", derived.read_text(encoding="utf-8") == original)
print("REPAIR_%s" % ("OK" if (derived.is_file()
                              and derived.read_text(encoding="utf-8") == original)
                      else "FAILED"))
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_brake_repair.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /root/_brake_repair.py", timeout=300)
c.close()
