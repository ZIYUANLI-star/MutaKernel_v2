"""Verify resume dedup + throughput improvement after cache fix."""
import time
import _remote as R

OUT = "/root/mk_v2_runs/e3_campaign"
c = R.connect()
print("### duplicate stable-key check over full ledger")
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json, collections\n"
         "keys=collections.Counter()\n"
         "for l in open('" + OUT + "/lane_m_run/observations.jsonl'):\n"
         "    if not l.strip(): continue\n"
         "    r=json.loads(l)\n"
         "    keys[(r['subject_id'], r['strategy_id'], r.get('test_id'), r.get('replicate'))]+=1\n"
         "dups={k:v for k,v in keys.items() if v>1}\n"
         "print('rows', sum(keys.values()), 'unique', len(keys), 'dup keys', len(dups))\n"
         "for k,v in list(dups.items())[:5]: print(' DUP', v, k[:2])\n"
         "EOF", timeout=300)
print("### 5-minute throughput sample")
R.run(c, f"a=$(wc -l < {OUT}/lane_m_run/observations.jsonl); sleep 300; "
         f"b=$(wc -l < {OUT}/lane_m_run/observations.jsonl); "
         f"echo rows_before=$a rows_after=$b delta_5min=$((b-a))", timeout=400)
print("### GPU + extensions dirs")
R.run(c, "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader; "
         "ls /root/mk_v2_runs/e3_campaign/lane_m_run/torch_extensions/ | wc -l", timeout=60)
print("### fresh-compile fraction in newest 20 worker logs")
R.run(c, "cd /root/mk_v2_runs/e3_campaign/lane_m_run/worker_logs && "
         "recent=$(ls -t | head -20) && b=0; t=0; "
         "for f in $recent; do t=$((t+1)); "
         "if grep -q 'Building extension module' $f 2>/dev/null; then b=$((b+1)); fi; done; "
         "echo recent=$t fresh_compiles=$b", timeout=120)
c.close()
print("VERIFY_DONE")
