"""Find where 'PROVEN'/proof markers actually live in the E1 ledgers."""
import _remote as R

c = R.connect()
cmds = [
    "grep -o -i 'proven[a-z_]*' /root/mk_v2_runs/e1/baseline_observations.jsonl | sort | uniq -c",
    "grep -i -m2 'proven' /root/mk_v2_runs/e1/baseline_summary.json",
    "grep -o -i '\"status\": \"[a-z_]*\"' /root/mk_v2_runs/e1/baseline_observations.jsonl | sort | uniq -c",
    "grep -i -m1 -o 'proof[a-zA-Z_\": ]\\{0,80\\}' /root/mk_v2_runs/e1/probe_manifest.json",
]
for cmd in cmds:
    print("### " + cmd[:90])
    R.run(c, cmd, timeout=120)
c.close()
print("GREP_DONE")
