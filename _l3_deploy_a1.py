"""A1: deploy the 50 vendored KernelBench level3 task files to the remote tree.

Pure file transfer: no GPU, no process started, nothing on the critical path.
The remote vendored tree already carries level1/level2 byte-identically to the
local copy (200/200 sha256 matches), so the level3 files uploaded here come from
the same upstream revision as the 200 contracts already extracted.

Verification is per file on the remote side (sha256 read back from disk), plus a
directory count and a re-check that level1/level2 were not touched.  Nothing
downstream runs: the contract re-extraction waits for a human go-ahead.
"""
import hashlib
import io
import json
from pathlib import Path

import _remote

LOCAL = Path(__file__).resolve().parent / "KernelBench" / "KernelBench" / "level3"
REMOTE_DIR = "/root/mk_v2/KernelBench/KernelBench/level3"

VERIFY = r'''
import hashlib, json, sys
from pathlib import Path

root = Path("/root/mk_v2/KernelBench/KernelBench")
out = {}
for lvl in ("level1", "level2", "level3"):
    d = root / lvl
    out[lvl] = ({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(d.glob("*.py"))} if d.is_dir() else None)
print("REMOTE_JSON " + json.dumps(out))
'''


def main():
    local = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(LOCAL.glob("*.py"))}
    print("local level3: %d files" % len(local))

    c = _remote.connect()
    sftp = c.open_sftp()
    _remote.run(c, "mkdir -p %s && echo MKDIR_OK" % REMOTE_DIR, timeout=120)
    for name in sorted(local, key=lambda n: int(n.split("_", 1)[0])):
        sftp.put(str(LOCAL / name), "%s/%s" % (REMOTE_DIR, name))
    print("uploaded %d files -> %s" % (len(local), REMOTE_DIR))
    sftp.putfo(io.BytesIO(VERIFY.encode()), "/root/_l3_verify.py")
    sftp.close()

    _code, stdout, _err = _remote.run(
        c, "/root/miniconda3/bin/python /root/_l3_verify.py", timeout=600,
        echo=False)
    c.close()

    remote = None
    for line in stdout.splitlines():
        if line.startswith("REMOTE_JSON "):
            remote = json.loads(line[len("REMOTE_JSON "):])
    if remote is None:
        print("no verification payload; raw:", stdout[:1500])
        return 1

    r3 = remote.get("level3") or {}
    missing = sorted(set(local) - set(r3))
    extra = sorted(set(r3) - set(local))
    differing = sorted(n for n in set(local) & set(r3) if local[n] != r3[n])
    print("\n== level3 verification ==")
    print("local=%d remote=%d missing=%d extra=%d differing=%d"
          % (len(local), len(r3), len(missing), len(extra), len(differing)))
    for label, names in (("missing", missing), ("extra", extra),
                         ("differing", differing)):
        for name in names[:10]:
            print("   %s: %s" % (label, name))

    print("\n== level1/level2 untouched? ==")
    local_root = LOCAL.parent
    ok = True
    for lvl in ("level1", "level2"):
        lo = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted((local_root / lvl).glob("*.py"))}
        re_ = remote.get(lvl) or {}
        bad = sorted(n for n in set(lo) & set(re_) if lo[n] != re_[n])
        print("   %s: local=%d remote=%d differing=%d" % (lvl, len(lo), len(re_),
                                                          len(bad)))
        ok = ok and not bad and len(lo) == len(re_)

    verdict = (len(local) == len(r3) == 50 and not missing and not extra
               and not differing and ok)
    manifest = {
        "step": "A1 deploy vendored KernelBench level3 to the remote tree",
        "remote_dir": REMOTE_DIR,
        "files": len(r3),
        "sha256_verified": verdict,
        "level3_sha256": r3,
    }
    Path("_l3_deploy_a1_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print("\nA1_%s (wrote _l3_deploy_a1_manifest.json)"
          % ("VERIFIED" if verdict else "FAILED"))
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
