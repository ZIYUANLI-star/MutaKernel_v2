import _remote

c = _remote.connect()
for cmd in [
    # imports of both drivers
    "sed -n '1,60p' /root/mk_v2/scripts/run_e1_cse_falsify.py",
    # run_worker definition
    "grep -n 'def run_worker\\|MK_WORKER_PATH\\|def _load_probe_files\\|def _resolve_problem_file\\|EQUIV_RUNS =\\|EQUIV_BASE_SEED =\\|FALSIFY_BASE_SEED\\|FALSIFY_EQUIV_RUNS\\|FALSIFY_STRESS_REPEATS\\|EQUIV_ROUND_TIMEOUT_S' /root/mk_v2/scripts/*.py /root/mk_v2/src/e1/*.py 2>/dev/null | head -40",
    # worker stress seeding
    "sed -n '690,745p' /root/mk_v2/scripts/_mutant_worker.py",
    # the two target records
    "grep -h 'L1_P46__index_replace__5' /root/mk_v2_runs/e1/cse_observations_lane*.jsonl | /root/miniconda3/bin/python -c \"import sys,json; [print(json.dumps({k:v for k,v in json.loads(l).items() if k in ('probe_id','outcome','witness_policy','witness_policy_sub','witness_seed','witness_round','divergence','finished_at')},ensure_ascii=False)) for l in sys.stdin]\"",
    "grep -h 'L1_P95__relop_replace__5' /root/mk_v2_runs/e1/equiv_observations*.jsonl 2>/dev/null | head -3",
    # the 7 INC records presence check
    "for p in L1_P96__launch_config_mutate__0 L1_P53__arith_replace__17 L1_P53__relop_replace__4 L1_P53__const_perturb__0 L1_P52__arith_replace__11 L1_P46__relop_replace__5; do echo -n \"$p lane3: \"; grep -c \"\\\"$p\\\"\" /root/mk_v2_runs/e1/cse_observations_lane3.jsonl; done; echo -n 'L1_P23__mask_boundary__1 lane5: '; grep -c 'L1_P23__mask_boundary__1' /root/mk_v2_runs/e1/cse_observations_lane5.jsonl",
    # lane3 remaining
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "plan=json.load(open('/root/mk_v2_runs/e1/cse_lane_plan.json'))\n"
    "k3=plan['lanes'][3]['kernels'] if isinstance(plan['lanes'],list) else plan['lanes']['3']['kernels']\n"
    "print('lane3 kernels n=',len(k3))\n"
    "EOF",
    # existing archives naming
    "ls /root/mk_v2_runs/e1/ | grep -i 'archive\\|inc_'",
]:
    print("### " + cmd.split("\n")[0][:90])
    _remote.run(c, cmd, timeout=120)
c.close()
print("FW4_DONE")
