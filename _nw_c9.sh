cd /root/mk_v2
echo '=== _b9_stage1_chain.py head + needles ==='
sed -n '1,60p' _b9_stage1_chain.py
echo '...'
grep -n 'NEEDLE\|needle\|_mutant_worker\|run_e1_cse_falsify\|_signoff_orch\|SIGNOFF\|pgrep\|nvidia-smi\|def main' _b9_stage1_chain.py
echo '=== keepalive_chain.sh ==='
cat /root/mk_v2_runs/e3_b9_calib/keepalive_chain.sh
echo '=== stage1 chain log tail ==='
tail -15 /root/mk_v2_runs/e3_b9_calib/stage1_chain_stdout.log 2>&1
echo '=== all b9 procs alive ==='
ps -o pid=,ppid=,stat=,etime=,cmd= -p 277742 279811 2>/dev/null
/root/miniconda3/bin/python - <<'PY'
import os
from pathlib import Path
for e in os.listdir('/proc'):
    if not e.isdigit(): continue
    p=int(e)
    try: c=Path('/proc/%d/cmdline'%p).read_bytes().replace(b'\0',b' ').decode('utf-8','replace').strip()
    except OSError: continue
    if 'b9' in c or 'keepalive' in c:
        print(p, c[:170])
PY
