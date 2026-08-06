echo '=== signoff orch log tail ==='
tail -40 /root/mk_v2_runs/signoff_orch.log
echo '=== running procs (proc scan, no pgrep -f) ==='
/root/miniconda3/bin/python - <<'PY'
import os
from pathlib import Path
excl=set()
pid=os.getpid()
def ppid(p):
    try:
        for l in open('/proc/%d/status'%p):
            if l.startswith('PPid:'): return int(l.split()[1])
    except OSError: pass
    return 0
while pid and pid!=1:
    excl.add(pid); pid=ppid(pid)
needles=('_mutant_worker.py','run_e1_cse_falsify.py','_signoff_orch.py','_b9_chain_trigger.py','_b9_calib_driver','guard_b9','e1_sentinel')
for e in os.listdir('/proc'):
    if not e.isdigit(): continue
    p=int(e)
    if p in excl: continue
    try: raw=Path('/proc/%d/cmdline'%p).read_bytes()
    except OSError: continue
    c=raw.replace(b'\0',b' ').decode('utf-8','replace').strip()
    if any(n in c for n in needles):
        print(p, c[:150])
PY
echo '=== gpu ==='
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader
for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader); do ps -o pid=,etime=,cmd= -p $p; done
echo '=== tagged obs files ==='
ls -la /root/mk_v2_runs/e1/cse_observations_lane3_signoff*.jsonl /root/mk_v2_runs/e1/cse_completed_lane3_signoff*.json 2>&1
echo '=== driver log tail ==='
ls -la /root/mk_v2_runs/e1_cse_lane3_signoff*.log 2>&1
tail -6 /root/mk_v2_runs/e1_cse_lane3_signoff_requeue.log 2>&1
echo '=== review dir ==='
ls -la /root/mk_v2_runs/e1/final_window_review/ 2>&1
