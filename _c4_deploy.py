"""Deploy C4 TritonBench-G corpus + manifest to remote (B1 of the gap plan)."""
import hashlib
import io
import os
import tarfile
import _remote

SRC_DIR = "external/C4_tritonbench/data/TritonBench_G_v1"
SRC_MAN = "external/C4_tritonbench/data/TritonBench_G_v1.json"
DST_TAR = "/tmp/c4_corpus.tar.gz"
DST_DIR = "/root/mk_v2/external/C4_tritonbench/data"

buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz") as tf:
    tf.add(SRC_DIR, arcname="TritonBench_G_v1")
    tf.add(SRC_MAN, arcname="TritonBench_G_v1.json")
buf.seek(0)
print("tar size: %.1f MB" % (len(buf.getvalue()) / 1e6))

local_sums = {}
for name in sorted(os.listdir(SRC_DIR)):
    with open(os.path.join(SRC_DIR, name), "rb") as fh:
        local_sums[name] = hashlib.sha256(fh.read()).hexdigest()
local_sums["__manifest__"] = hashlib.sha256(open(SRC_MAN, "rb").read()).hexdigest()
print("local files:", len(local_sums) - 1)

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(buf, DST_TAR)
sftp.close()

_, o, e = _remote.run(c, (
    "mkdir -p %s && cd %s && tar xzf %s && "
    "ls TritonBench_G_v1 | wc -l && sha256sum TritonBench_G_v1.json"
    % (DST_DIR, DST_DIR, DST_TAR)), timeout=120, echo=False)
print(o, e)

# remote-side verification
CMD = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import hashlib, os, json\n"
    "d = '%s/TritonBench_G_v1'\n"
    "sums = {}\n"
    "for n in sorted(os.listdir(d)):\n"
    "    sums[n] = hashlib.sha256(open(os.path.join(d, n), 'rb').read()).hexdigest()\n"
    "print(json.dumps({'count': len(sums), 'agg': hashlib.sha256(''.join('%%s %%s' %% kv for kv in sorted(sums.items())).encode()).hexdigest()}))\n"
    "EOF\n" % DST_DIR
)
_, o, _ = _remote.run(c, CMD, timeout=120, echo=False)
print("remote:", o.strip())
c.close()

import json as _json
agg_local = hashlib.sha256("".join(
    "%s %s" % kv for kv in sorted(
        (k, v) for k, v in local_sums.items() if k != "__manifest__"
    )).encode()).hexdigest()
remote = _json.loads(o.strip().splitlines()[-1])
print("local agg:", agg_local)
print("MATCH:", remote["agg"] == agg_local and remote["count"] == 184)
