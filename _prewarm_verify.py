"""Verify prewarm completion + runner speedup."""
import _remote as R

OUT = "/root/mk_v2_runs/e3_campaign"
c = R.connect()
print("### prewarm final status")
R.run(c, f"tail -2 {OUT}/prewarm_run.log; "
         f"/root/miniconda3/bin/python -c \"import json,collections\n"
         f"st=collections.Counter(json.loads(l)['status'] for l in open('{OUT}/lane_m_run/prewarm_log.jsonl'))\n"
         f"print('prewarm statuses:', dict(st))\"; "
         f"ls {OUT}/lane_m_run/torch_extensions/ | wc -l; uptime", timeout=60)
print("### runner rows in the last 10 minutes: wall times")
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json, time, statistics, collections\n"
         "OUT='" + OUT + "/lane_m_run'\n"
         "import subprocess\n"
         "rows=[json.loads(l) for l in open(OUT+'/observations.jsonl') if l.strip()]\n"
         "print('total rows:', len(rows))\n"
         "recent=rows[-40:]\n"
         "w=sorted(r['parent_wall_ms']/1000 for r in recent)\n"
         "print('recent-40 wall: median', round(w[len(w)//2],1), 's mean',\n"
         "      round(statistics.mean(w),1), 's max', round(w[-1],1), 's')\n"
         "EOF", timeout=120)
print("### 3-min throughput")
R.run(c, f"a=$(wc -l < {OUT}/lane_m_run/observations.jsonl); sleep 180; "
         f"b=$(wc -l < {OUT}/lane_m_run/observations.jsonl); echo delta_3min=$((b-a))", timeout=250)
c.close()
print("VERIFY_DONE")
