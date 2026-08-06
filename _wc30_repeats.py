import _remote
c = _remote.connect()
R = _remote.run
script = r'''
import json, collections, glob, os
E1 = "/root/mk_v2_runs/e1"
def scan(paths, tag):
    si = collections.Counter()
    pol = collections.Counter()
    for p in paths:
        for line in open(p):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            for t in (r.get("trials") or []):
                if t.get("round_type") == "stress":
                    si[t.get("sub_index")] += 1
                    pol[t.get("policy")] += 1
    print(tag, "stress sub_index histogram:", dict(sorted(si.items(), key=lambda x: str(x[0]))))
    print(tag, "n distinct policies:", len(pol))
scan([E1 + "/equiv_observations.jsonl"], "equiv")
ARCH = (".bak", "_env_v1", "_inc_archive", "_timeout_v1", "_signoff_archive")
cse = [p for p in sorted(glob.glob(E1 + "/cse_observations*.jsonl"))
       if not any(h in os.path.basename(p) for h in ARCH)]
scan(cse, "cse")
'''
open("_wc30_tmp.py","w").write(script)
s = c.open_sftp(); s.put("_wc30_tmp.py", "/root/mk_v2/_wc30_tmp.py"); s.close()
R(c, "/root/miniconda3/bin/python /root/mk_v2/_wc30_tmp.py", timeout=600)
c.close()
