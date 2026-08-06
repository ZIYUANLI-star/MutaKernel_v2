"""Wider search for machine-proof + replay bundle artifacts."""
import _remote as R

c = R.connect()
cmds = [
    "grep -rl -i 'PROVEN' /root/mk_v2_runs/e1/ --include='*.jsonl' --include='*.json' 2>/dev/null | head",
    "grep -l -i 'proof' /root/mk_v2_runs/e1/*.json /root/mk_v2_runs/e1/analysis/final/* 2>/dev/null | head",
    "find /root/mk_v2_runs -maxdepth 3 -iname '*replay*' -o -maxdepth 3 -iname '*bundle*' -o -maxdepth 3 -iname '*proof*' 2>/dev/null | head -20",
    "grep -i -m3 'machine' /root/mk_v2_runs/e1/analysis/final/*.json 2>/dev/null | head",
    "ls /root/mk_v2_runs/e1/analysis/final/",
]
for cmd in cmds:
    print("### " + cmd[:90])
    R.run(c, cmd, timeout=180)
c.close()
print("LOCATE2_DONE")
