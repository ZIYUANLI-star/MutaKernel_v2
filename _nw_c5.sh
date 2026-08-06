cd /root/mk_v2
echo '=== run_worker ==='
grep -n 'def run_worker' -A 45 scripts/run_e1_probe_study.py
echo '=== _load_probe_files / _resolve_problem_file ==='
grep -n 'def _load_probe_files' -A 25 scripts/run_e1_probe_study.py
grep -n 'def _resolve_problem_file' -A 20 scripts/run_e1_probe_study.py
echo '=== P37 problem file get_inputs ==='
find /root/mk_v2/KernelBench -path '*level1*' -name '37_*' | head
echo '=== p37_cluster review summary ==='
cat /root/mk_v2_runs/e1/final_window_review/p37_cluster/review_summary.json
