import _remote
c = _remote.connect()
R = _remote.run
print("===== _cse_agg2.py =====")
R(c, "cat /root/mk_v2/_cse_agg2.py")
print("===== signoff_orch_summary.json =====")
R(c, "cat /root/mk_v2_runs/e1/signoff_orch_summary.json")
print("===== equiv_summary.json =====")
R(c, "cat /root/mk_v2_runs/e1/equiv_summary.json; echo; cat /root/mk_v2_runs/e1/equiv_observations_signoff_archive_v1.jsonl | head -c 1200")
c.close()
print("DONE")
