"""Upload sign-off script, patch driver round-timeout override, run ledger steps,
then launch the signoff_requeue rerun driver in the background."""
import _remote

PATCH = r'''
import re
p = "/root/mk_v2/scripts/run_e1_cse_falsify.py"
src = open(p, encoding="utf-8").read()
OLD = '"round_timeout": EQUIV_ROUND_TIMEOUT_S,'
NEW = ('"round_timeout": int(os.environ.get("MK_CSE_ROUND_TIMEOUT",\n'
       '                                                 EQUIV_ROUND_TIMEOUT_S)),')
if "MK_CSE_ROUND_TIMEOUT" in src:
    print("driver already patched")
else:
    assert OLD in src, "anchor not found"
    assert "import os" in src, "os not imported"
    open(p + ".bak_signoff", "w", encoding="utf-8").write(src)
    open(p, "w", encoding="utf-8").write(src.replace(OLD, NEW, 1))
    print("driver patched: round_timeout env override MK_CSE_ROUND_TIMEOUT")
import py_compile; py_compile.compile(p, doraise=True); print("compile OK")
'''

ENV = ("PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin "
       "TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext "
       "MK_GPU_MEMORY_FRACTION=0.92 MK_CSE_ROUND_TIMEOUT=300")
LAUNCH = (
    "cd /root/mk_v2 && " + ENV +
    " nohup /root/miniconda3/bin/python -u scripts/run_e1_cse_falsify.py"
    " --out-dir /root/mk_v2_runs/e1 --kernelbench-root KernelBench"
    " --timeout 3600 --lane-plan /root/mk_v2_runs/e1/cse_lane_plan.json"
    " --lane 3 --lane-tag signoff_requeue"
    " >> /root/mk_v2_runs/e1_cse_lane3_signoff_requeue.log 2>&1 & echo LAUNCHED $!"
)

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_signoff_go_remote.py", "/root/mk_v2/_signoff_go_remote.py")
with sftp.open("/root/mk_v2/_signoff_patch_driver.py", "w") as f:
    f.write(PATCH)
sftp.close()
print("== patch driver ==")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _signoff_patch_driver.py",
            timeout=120)
print("== ledger steps ==")
code, out, _ = _remote.run(
    c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _signoff_go_remote.py",
    timeout=300)
if "SIGNOFF_LEDGER_DONE" not in out:
    print("!! ledger step failed, NOT launching driver")
    c.close()
    raise SystemExit(1)
print("== launch rerun driver ==")
_remote.run(c, LAUNCH, timeout=60)
import time
time.sleep(8)
_remote.run(c, "ps aux | grep 'run_e1_cse_falsify.py.*signoff_[r]equeue'; "
               "tail -5 /root/mk_v2_runs/e1_cse_lane3_signoff_requeue.log", timeout=60)
c.close()
print("SIGNOFF_RUN_DONE")
