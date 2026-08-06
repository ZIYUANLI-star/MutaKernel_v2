"""Upload the sign-off script, pre-flight check, and launch under nohup."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_signoff_go_remote.py", "/root/mk_v2/_signoff_go.py")
sftp.close()
print("uploaded")

_remote.run(c, (
    "cd /root/mk_v2 && /root/miniconda3/bin/python -m py_compile _signoff_go.py "
    "&& echo COMPILE_OK; "
    "grep -c 'import os' scripts/run_e1_cse_falsify.py; "
    "grep -n '\"round_timeout\": EQUIV_ROUND_TIMEOUT_S,' scripts/run_e1_cse_falsify.py"
), timeout=120)

_remote.run(c, (
    "cd /root/mk_v2 && nohup /root/miniconda3/bin/python -u _signoff_go.py "
    "> /root/mk_v2_runs/signoff_go.log 2>&1 & echo LAUNCHED_PID=$!; sleep 8; "
    "tail -30 /root/mk_v2_runs/signoff_go.log"
), timeout=120)
c.close()
print("LAUNCH_DONE")
