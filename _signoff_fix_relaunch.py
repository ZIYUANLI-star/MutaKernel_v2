"""Stop the just-started driver, fix the round-timeout patch (add import os),
check provenance of the pre-applied A/B amendments, then relaunch."""
import time

import _remote

PATCH2 = r'''
import re
p = "/root/mk_v2/scripts/run_e1_cse_falsify.py"
src = open(p, encoding="utf-8").read()
changed = False
if "\nimport os\n" not in src:
    # insert after the first import block line "import json" or "import argparse"
    for anchor in ("\nimport json\n", "\nimport argparse\n"):
        if anchor in src:
            src = src.replace(anchor, anchor + "import os\n", 1)
            changed = True
            break
    assert changed, "no import anchor found"
OLD = '"round_timeout": EQUIV_ROUND_TIMEOUT_S,'
if "MK_CSE_ROUND_TIMEOUT" not in src:
    assert OLD in src, "round_timeout anchor not found"
    src = src.replace(OLD, '"round_timeout": int(os.environ.get("MK_CSE_ROUND_TIMEOUT", EQUIV_ROUND_TIMEOUT_S)),', 1)
    changed = True
if changed:
    import shutil
    shutil.copy2(p, p + ".bak_signoff_patch")
    open(p, "w", encoding="utf-8").write(src)
import py_compile; py_compile.compile(p, doraise=True)
print("PATCH_OK changed=", changed)
print([l for l in src.splitlines() if "MK_CSE_ROUND_TIMEOUT" in l])
'''

PROV = r'''
import json
base = "/root/mk_v2_runs/e1/"
for line in open(base + "equiv_observations.jsonl", encoding="utf-8"):
    r = json.loads(line)
    if r.get("probe_id") == "L1_P95__relop_replace__5":
        print("P95 signoff field:", json.dumps(r.get("signoff"), ensure_ascii=False))
        print("P95 witness field:", json.dumps(r.get("witness"), ensure_ascii=False)[:400])
raw = json.loads(open(base + "cse_policy_skip.json", encoding="utf-8").read())
print("p37 reason present:", "p37_reason" in raw, str(raw.get("p37_reason"))[:200])
import subprocess
out = subprocess.run(["grep", "-rn", "bak_signoff", "/root/mk_v2/", "--include=*.py", "-l"],
                     capture_output=True, text=True).stdout
print("scripts mentioning bak_signoff:", out.strip())
'''

c = _remote.connect()
print("== kill driver ==")
_remote.run(c, "pkill -f 'signoff_requeue' ; sleep 2; ps aux | grep 'signoff_[r]equeue' | wc -l; "
               "cat /root/mk_v2_runs/e1/cse_completed_lane3_signoff_requeue.json 2>/dev/null; "
               "wc -l /root/mk_v2_runs/e1/cse_observations_lane3_signoff_requeue.jsonl 2>/dev/null",
            timeout=60)
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_signoff_patch2.py", "w") as f:
    f.write(PATCH2)
with sftp.open("/root/mk_v2/_signoff_prov.py", "w") as f:
    f.write(PROV)
sftp.close()
print("== patch driver (v2) ==")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _signoff_patch2.py", timeout=120)
print("== provenance of pre-applied A/B ==")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _signoff_prov.py", timeout=120)
print("== relaunch ==")
ENV = ("PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin "
       "TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext "
       "MK_GPU_MEMORY_FRACTION=0.92 MK_CSE_ROUND_TIMEOUT=300")
_remote.run(c, "cd /root/mk_v2 && " + ENV +
            " nohup /root/miniconda3/bin/python -u scripts/run_e1_cse_falsify.py"
            " --out-dir /root/mk_v2_runs/e1 --kernelbench-root KernelBench"
            " --timeout 3600 --lane-plan /root/mk_v2_runs/e1/cse_lane_plan.json"
            " --lane 3 --lane-tag signoff_requeue"
            " >> /root/mk_v2_runs/e1_cse_lane3_signoff_requeue.log 2>&1 "
            "& echo LAUNCHED_PID $! ; sleep 1", timeout=60)
time.sleep(8)
_remote.run(c, "ps aux | grep 'signoff_[r]equeue' | grep -v grep | wc -l; "
               "tail -5 /root/mk_v2_runs/e1_cse_lane3_signoff_requeue.log", timeout=60)
c.close()
print("FIX_RELAUNCH_DONE")
