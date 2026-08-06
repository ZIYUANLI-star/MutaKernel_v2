"""Fix 1: verify zero refs to repo-internal C5 staging, then move it out."""
import _remote as R

c = R.connect()
print("### references to repo-internal C5 staging in wave2 artifacts")
R.run(c, "grep -rl 'external/C5_kernelbench_samples_wave2\\|external/c5_wave2' "
         "/root/mk_v2_runs/e3_campaign/wave2_subject_manifest.json "
         "/root/mk_v2_runs/e3_campaign/wave2_lane_m_plan.json "
         "/root/mk_v2_runs/e3_campaign/wave2_mdir_plan.json "
         "/root/mk_v2_runs/e3_campaign/wave2_subjects.jsonl "
         "/root/mk_v2_runs/e3_campaign/wave2_manifest_input.jsonl 2>/dev/null; "
         "echo grep_exit=$?", timeout=120)
print("### where the c5_wave2 staged copies actually live")
R.run(c, "ls /root/mk_v2_runs/e3_corpora/ 2>/dev/null; "
         "ls /root/mk_v2_runs/e3_corpora/c5_wave2/ 2>/dev/null | head -5", timeout=60)
c.close()
print("FIX1_CHECK_DONE")
