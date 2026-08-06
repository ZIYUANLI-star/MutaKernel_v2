"""Afternoon sweep: WC final analysis, ledger amendments, B9 progress."""
import _remote

CMD1 = (
    "date '+NOW=%F %T'; echo SEP; "
    "ls -la /root/mk_v2_runs/e1/witness_confirmation/ | grep -vE 'cells|scratch'; echo SEP; "
    "ls -la /root/mk_v2_runs/e1/ | grep -iE 'wc|witness|amend|ruling|signoff' ; echo SEP; "
    "ls -lat /root/mk_v2_runs/e1/*.json /root/mk_v2_runs/e1/*.jsonl 2>/dev/null | head -15; echo SEP; "
    "cat /root/mk_v2_runs/e1/equiv_summary.json 2>/dev/null | head -c 1500"
)

CMD2 = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json, glob\n"
    "from collections import Counter\n"
    "E1='/root/mk_v2_runs/e1/'\n"
    "# CSE ledger current state\n"
    "cse={}\n"
    "for p in sorted(glob.glob(E1+'cse_observations_lane*.jsonl')):\n"
    "    if '.bak' in p: continue\n"
    "    for l in open(p):\n"
    "        if l.strip():\n"
    "            r=json.loads(l)\n"
    "            if r.get('outcome')!='INCONCLUSIVE' or ('archive' not in p and 'timeout_v1' not in p):\n"
    "                cse[r['probe_id']]=r.get('outcome')\n"
    "print('CSE:', dict(Counter(cse.values())), 'n=', len(cse))\n"
    "eq=[json.loads(l) for l in open(E1+'equiv_observations.jsonl') if l.strip()]\n"
    "print('EQUIV:', dict(Counter(r.get('evidence_grade') for r in eq)), 'n=', len(eq))\n"
    "# any wc analysis outputs\n"
    "import os\n"
    "for f in sorted(glob.glob(E1+'witness_confirmation/*.json')):\n"
    "    print('WCFILE', os.path.basename(f), os.path.getmtime(f))\n"
    "EOF\n"
)

CMD3 = (
    "tail -n 6 /root/mk_v2_runs/e3_b9_calib/stage1_chain.log; echo SEP; "
    "/root/miniconda3/bin/python -c \"import json; from collections import Counter; "
    "qs=json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json')); "
    "d=qs['done']; print('wave', qs.get('wave'), 'done', len(d), 'pending', len(qs.get('pending',[])), "
    "'claimed', list(qs.get('claimed',{}))); print(dict(Counter(d.values())))\"; echo SEP; "
    "grep -H oom_kill /sys/fs/cgroup/memory/memory.oom_control; "
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; "
    "tail -c 300 /root/mk_v2_runs/e1_sentinel.log"
)

c = _remote.connect()
print("##### WC / LEDGERS #####")
_, o, _ = _remote.run(c, CMD1, timeout=120, echo=False)
print(o)
print("##### TALLIES #####")
_, o, _ = _remote.run(c, CMD2, timeout=240, echo=False)
print(o)
print("##### B9 / SYSTEM #####")
_, o, _ = _remote.run(c, CMD3, timeout=120, echo=False)
c.close()
print(o)
print("AFTERNOON_DONE")
