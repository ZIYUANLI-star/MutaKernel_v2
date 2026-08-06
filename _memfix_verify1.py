#!/usr/bin/env python3
import _remote

c = _remote.connect()
r = lambda cmd, t=120: _remote.run(c, cmd, timeout=t)
r("/root/miniconda3/bin/python -c \"import json; "
  "m=json.load(open('/root/mk_v2_runs/e1/cse_run_manifest_lane3.json')); "
  "print('lane3', m['run_id'], m['started_at']); "
  "print(' pipeline:', m['input_pipeline'][:100]); "
  "m5=json.load(open('/root/mk_v2_runs/e1/cse_run_manifest_lane5.json')); "
  "print('lane5', m5['run_id'], m5['started_at']); "
  "print(' pipeline:', m5['input_pipeline'][:100])\"")
r("pgrep -af 'scripts/_mutant_worker.py' | sed 's/.*cfg_/worker: /;s/\\.json.*//'")
c.close()
