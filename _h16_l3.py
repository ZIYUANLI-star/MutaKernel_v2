"""Count the L3 contract gap and locate the C4 draft."""
import io

import _remote

SCRIPT = r'''
import json, collections
from pathlib import Path
d = json.loads(Path("/root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_draft.freeze.json").read_text())
f = d["failures"]
print("== contract extraction failures:", len(f))
lv = collections.Counter(x["task_id"].split("_")[0] for x in f)
print("   by level:", dict(lv))
err = collections.Counter(x["error"][:60] for x in f)
print("   by error:", dict(err))
sc = collections.Counter(tuple(sorted(x.get("source_corpora", []))) for x in f)
print("   by source corpora:", {str(k): v for k, v in sc.items()})
print("   contracts extracted:", d["contracts"])
print("   total tasks referenced by C2/C3/C5:", d["contracts"] + len(f))
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_h16.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /root/_h16.py", timeout=300)
print("\n#### search the whole box for a C4 / tritonbench contract draft")
_remote.run(c, "find / -xdev -name 'contracts_c4*' 2>/dev/null; "
               "ls /root/mk_v2 | head -40", timeout=300)
c.close()
print("\nH16_DONE")
