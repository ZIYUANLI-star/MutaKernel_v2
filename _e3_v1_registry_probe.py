"""Probe V1 ai_cuda_engineer registry entries + run_quick_baseline flow."""
import _remote as R

py = r"""
import json
from pathlib import Path
reg = json.load(open('/root/mk_v2/external_benchmarks/ai_cuda_engineer/registry.json'))
print('entries:', len(reg))
r = reg[0]
for k, v in r.items():
    print('%-24s %s' % (k, str(v)[:130].replace('\n', ' | ')))
d = Path('/root/mk_v2/external_benchmarks/ai_cuda_engineer')
for p in sorted(d.iterdir())[:10]:
    print('DIR:', p.name)
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_e3_v1reg.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _e3_v1reg.py",
      timeout=120)
R.run(c, "grep -n 'def run_quick_baseline' -A 40 "
         "/root/mk_v2/scripts/run_fullscale_diff_test.py | head -60", timeout=60)
c.close()
print("DONE")
