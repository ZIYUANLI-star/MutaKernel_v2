ls -la /root/mk_v2_runs/e1/final_window_review/p37_sync_remove_1_newwitness/ 2>&1
echo '--- log ---'
cat /root/mk_v2_runs/e1/final_window_review/p37_sync_remove_1_newwitness/review.log 2>&1
echo '--- stdout ---'
tail -20 /root/mk_v2_runs/e1/p37_newwitness_stdout.log 2>&1
echo '--- proc ---'
/root/miniconda3/bin/python - <<'PY'
import os
from pathlib import Path
for e in sorted(os.listdir('/proc')):
    if not e.isdigit(): continue
    p=int(e)
    try: c=Path('/proc/%d/cmdline'%p).read_bytes().replace(b'\0',b' ').decode('utf-8','replace').strip()
    except OSError: continue
    if 'newwitness' in c:
        print(p, c[:160])
PY
