import _remote

CMD = (
    "head -c 600 /root/mk_v2_runs/e1_cse_lane0.log; echo; echo SEP; "
    "cat /root/mk_v2_runs/e1/cse_lane_plan.json | head -c 1200; echo SEP; "
    "ls /root/mk_v2_runs/e1/ | grep -i 'merge\\|final'; echo SEP; "
    "cat /root/mk_v2_runs/e1/equiv_merge_report.json 2>/dev/null | head -c 1500; echo SEP; "
    # grade mix in each cse lane so far
    "for f in /root/mk_v2_runs/e1/cse_observations_lane*.jsonl; do echo \"== $f\"; "
    "grep -o '\"cse_grade\": \"[A-Z_]*\"' $f | sort | uniq -c; "
    "grep -o '\"grade\": \"[A-Z_]*\"' $f | sort | uniq -c; done"
)

c = _remote.connect()
_, out, _ = _remote.run(c, CMD, timeout=120, echo=False)
c.close()
print(out)
