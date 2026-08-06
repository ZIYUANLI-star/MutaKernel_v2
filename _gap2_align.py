"""Version-align the local KernelBench vendored tree against the remote one.

Read-only: hashes level1/level2 on both sides and reports whether the local
level3 files can be treated as the same upstream revision as the vendored
level1/level2 already used for the 200 extracted contracts.
"""
import hashlib
import io
import json
from pathlib import Path

import _remote

LOCAL_ROOT = Path(__file__).resolve().parent / "KernelBench" / "KernelBench"

REMOTE = r'''
import hashlib, json
from pathlib import Path
root = Path("/root/mk_v2/KernelBench/KernelBench")
out = {}
for lvl in ("level1", "level2", "level3", "level4"):
    d = root / lvl
    if not d.is_dir():
        out[lvl] = None
        continue
    out[lvl] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(d.glob("*.py"))}
print("REMOTE_JSON " + json.dumps(out))
'''


def local_digests():
    out = {}
    for lvl in ("level1", "level2", "level3", "level4"):
        d = LOCAL_ROOT / lvl
        if not d.is_dir():
            out[lvl] = None
            continue
        out[lvl] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(d.glob("*.py"))}
    return out


def main():
    c = _remote.connect()
    sftp = c.open_sftp()
    sftp.putfo(io.BytesIO(REMOTE.encode()), "/root/_gap2_align.py")
    sftp.close()
    _code, stdout, _err = _remote.run(
        c, "/root/miniconda3/bin/python /root/_gap2_align.py", timeout=600,
        echo=False)
    c.close()

    remote = None
    for line in stdout.splitlines():
        if line.startswith("REMOTE_JSON "):
            remote = json.loads(line[len("REMOTE_JSON "):])
    if remote is None:
        print("no remote payload; raw:", stdout[:2000])
        return

    local = local_digests()
    for lvl in ("level1", "level2", "level3", "level4"):
        lo, re_ = local.get(lvl), remote.get(lvl)
        print("== %s: local=%s remote=%s" % (
            lvl, "absent" if lo is None else "%d files" % len(lo),
            "absent" if re_ is None else "%d files" % len(re_)))
        if not lo or not re_:
            continue
        only_local = sorted(set(lo) - set(re_))
        only_remote = sorted(set(re_) - set(lo))
        differing = sorted(n for n in set(lo) & set(re_) if lo[n] != re_[n])
        print("   only-local=%d only-remote=%d differing=%d identical=%d"
              % (len(only_local), len(only_remote), len(differing),
                 len(set(lo) & set(re_)) - len(differing)))
        for name in (only_local[:5] + only_remote[:5] + differing[:5]):
            print("    !", name)

    l3 = local.get("level3") or {}
    print("\n== local level3 inventory (%d files) ==" % len(l3))
    for name in sorted(l3, key=lambda n: int(n.split("_", 1)[0])):
        print("   %-70s %s" % (name, l3[name][:16]))
    manifest = {"level3": l3}
    Path("_l3_local_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print("\nwrote _l3_local_manifest.json")


if __name__ == "__main__":
    main()
