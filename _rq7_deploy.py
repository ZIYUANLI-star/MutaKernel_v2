"""Deploy and launch the requeue_final runner on the remote server."""
import time
import _remote

SRC = "_rq7_requeue_src.py"
DST = "/root/mk_v2/_rq7_requeue.py"

c = _remote.connect()

# preconditions: GPU idle, no drivers/orchestrators alive
_, o, _ = _remote.run(c, (
    "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader; "
    "pgrep -af '[_]b9_calib_driver_v2.py|[_]wcfu|[_]mutant_worker|[_]wc_audit' "
    "| head -5; echo PRECHECK_END"), timeout=60, echo=False)
print("PRECHECK:\n" + o)
if "PRECHECK_END" not in o:
    raise SystemExit("precheck failed to run")
lines = [ln for ln in o.splitlines() if ln.strip() and ln != "PRECHECK_END"]
gpu_line = lines[0] if lines else ""
proc_lines = [ln for ln in lines[1:] if ln.strip()]
if proc_lines:
    raise SystemExit("BLOCKED: experiment processes still alive: %r" % proc_lines)

sftp = c.open_sftp()
sftp.put(SRC, DST)
sftp.close()
print("uploaded", DST)

_, o, e = _remote.run(c, "/root/miniconda3/bin/python -m py_compile %s && echo COMPILE_OK" % DST,
                      timeout=60, echo=False)
print(o, e)
if "COMPILE_OK" not in o:
    raise SystemExit("compile failed")

_, o, _ = _remote.run(c, (
    "mkdir -p /root/mk_v2_runs/e1/requeue_final && cd /root/mk_v2 && "
    "nohup /root/miniconda3/bin/python -u _rq7_requeue.py "
    ">> /root/mk_v2_runs/e1/requeue_final/nohup.out 2>&1 < /dev/null & "
    "echo LAUNCHED_PID=$!"), timeout=30, echo=False)
print(o)

time.sleep(8)
_, o, _ = _remote.run(c, (
    "pgrep -af '[_]rq7_requeue.py'; echo ---; "
    "tail -5 /root/mk_v2_runs/e1/requeue_final/run.log 2>/dev/null; echo ---; "
    "tail -5 /root/mk_v2_runs/e1/requeue_final/nohup.out 2>/dev/null"),
    timeout=30, echo=False)
print("POSTCHECK:\n" + o)
c.close()
print("RQ7_DEPLOY_DONE")
