#!/usr/bin/env python3
"""Deploy cse_mem_fix_v1: ledger snapshot -> install -> full pytest ->
kill drivers-then-workers -> verify ledger -> guard AUTORESTART."""
import time

import _remote

c = _remote.connect()
r = lambda cmd, t=120: _remote.run(c, cmd, timeout=t)

print("### 1. pre-kill ledger snapshot")
r("wc -l /root/mk_v2_runs/e1/cse_observations_lane3.jsonl "
  "/root/mk_v2_runs/e1/cse_observations_lane5.jsonl")
r("md5sum /root/mk_v2_runs/e1/cse_completed_lane3.json "
  "/root/mk_v2_runs/e1/cse_completed_lane5.json")
r("ps -eo pid,args | grep _mutant_worker.py | grep -v grep | "
  "sed 's/.*cfg_/inflight: /;s/\\.json.*//'")
r("for p in L1_P46__relop_replace__0 L1_P23__init_modify__0; do "
  "echo -n \"$p in completed/obs: \"; "
  "grep -l $p /root/mk_v2_runs/e1/cse_completed_lane*.json "
  "/root/mk_v2_runs/e1/cse_observations_lane*.jsonl || echo NONE; done")

print("### 2. backup live files")
r("cd /root/mk_v2 && cp scripts/_mutant_worker.py "
  "scripts/_mutant_worker.py.bak_20260729_pre_mem_fix && "
  "cp scripts/run_e1_cse_falsify.py "
  "scripts/run_e1_cse_falsify.py.bak_20260729_pre_mem_fix && "
  "cp tests/test_gen_opt_bitexact.py "
  "tests/test_gen_opt_bitexact.py.bak_20260729_pre_mem_fix && echo BACKUP_OK")

print("### 3. atomic install (staging -> live via mv)")
r("cp /root/mk_v2_staging/_mutant_worker.py "
  "/root/mk_v2/scripts/.new_mutant_worker.py && "
  "mv -f /root/mk_v2/scripts/.new_mutant_worker.py "
  "/root/mk_v2/scripts/_mutant_worker.py && "
  "cp /root/mk_v2_staging/run_e1_cse_falsify.py "
  "/root/mk_v2/scripts/.new_run_e1_cse_falsify.py && "
  "mv -f /root/mk_v2/scripts/.new_run_e1_cse_falsify.py "
  "/root/mk_v2/scripts/run_e1_cse_falsify.py && "
  "cp /root/mk_v2_staging/test_gen_opt_bitexact.py "
  "/root/mk_v2/tests/test_gen_opt_bitexact.py && "
  "cp /root/mk_v2_staging/test_cse_memfix.py "
  "/root/mk_v2/tests/test_cse_memfix.py && echo INSTALL_OK")
r("md5sum /root/mk_v2/scripts/_mutant_worker.py "
  "/root/mk_v2/scripts/run_e1_cse_falsify.py "
  "/root/mk_v2_staging/_mutant_worker.py "
  "/root/mk_v2_staging/run_e1_cse_falsify.py")

print("### 4. live py_compile + full pytest")
r("cd /root/mk_v2 && /root/miniconda3/bin/python -m py_compile "
  "scripts/_mutant_worker.py scripts/run_e1_cse_falsify.py && "
  "echo LIVE_COMPILE_OK")
r("cd /root/mk_v2 && /root/miniconda3/bin/python -m pytest -q 2>&1 | tail -4",
  900)
c.close()
print("DEPLOY_PHASE1_DONE")
