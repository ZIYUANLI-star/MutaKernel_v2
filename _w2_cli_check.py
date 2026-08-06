import _remote as R

c = R.connect()
for f in ("/root/mk_v2_ops/build_wave15_lane_plans.py",
          "/root/mk_v2_ops/wave15_subset_analysis.py",
          "/root/mk_v2_ops/run_port_batch.py",
          "/root/mk_v2_ops/build_b9_tol_map.py",
          "/root/mk_v2_ops/wave15_orchestrator.py"):
    print("### " + f)
    R.run(c, f"grep -n 'add_argument\\|add_parser\\|set_defaults\\|def cmd_\\|def stage_\\|_DONE\\|CHAIN_DONE\\|lane_g_subjects\\|lane_la\\|lane_lb\\|subjects.txt' {f} | head -50",
          timeout=60)
c.close()
print("DONE")
