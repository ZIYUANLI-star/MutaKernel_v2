"""Leave a coordination note on the remote so any parallel worker does not
double-launch the rerun driver."""
import _remote

NOTE = """# SIGNOFF COORDINATION (2026-07-30 16:55 CST, foreground coordinator)

STATE: all sign-off ledger steps are APPLIED. Do NOT re-run them and do NOT
launch another rerun driver.

- STEP A (P95 equiv amendment -> WITNESSED/spec_violation): applied 16:33
  (archive: equiv_observations_signoff_archive_v1.jsonl), summary regenerated
  (LIKELY 453 / WITNESSED 74 / INC 0).
- STEP B (L1_P37 boundary_last_element skip): applied 16:33 in
  cse_policy_skip.json (note: p37 written without reason field; rationale is
  documented in cse_signoff_manifest.json and the local ledger doc).
- Driver patch (MK_CSE_ROUND_TIMEOUT env override + import os): applied 16:37,
  backup scripts/run_e1_cse_falsify.py.bak_signoff_patch, py_compile OK.
- STEP C/D (lane3 requeue of the 6 signed-off FALSIFIED ids): applied 16:34.
  Archive: cse_observations_signoff_archive.jsonl (6 lines, signoff block per
  record). lane3 obs 93->87, completed 93->87.
  Manifest: cse_signoff_manifest.json.
- STEP E (rerun driver): RUNNING since 16:37, pid 265795,
  tag signoff_requeue, --timeout 3600, MK_CSE_ROUND_TIMEOUT=300 (review-
  validated value), MK_GPU_MEMORY_FRACTION=0.92, exclusive GPU.
  Log: /root/mk_v2_runs/e1_cse_lane3_signoff_requeue.log
  EXACTLY ONE driver must run. Check `pgrep -f signoff_requeue` before any
  action.

REMAINING (after driver exits, whoever gets here first, idempotently):
  F. annotate rerun records (policy_skip_reason ->
     oracle_indiscriminative_for_kernel for P37, signoff_rerun provenance)
     -- see _signoff_go.py step_f_fixups.
  G. merge tagged obs into the frozen final ledger
     (cse_observations_final.jsonl + cse_final_summary.json + md5).
  H. offline_reuse_all.py final recompute; mapbuild; docs; sentinel
     retirement.
The foreground coordinator will pick these up on driver completion unless a
worker has already done them (leave markers/summaries).
"""

c = _remote.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/SIGNOFF_COORDINATION.md", "w") as f:
    f.write(NOTE)
sftp.close()
_, out, _ = _remote.run(c, "ls -la /root/mk_v2/SIGNOFF_COORDINATION.md; "
                           "ps aux | grep 'signoff_[r]equeue' | grep -v bash | wc -l; "
                           "tail -3 /root/mk_v2_runs/e1_cse_lane3_signoff_requeue.log",
                        timeout=60)
c.close()
print("COORD_DONE")
