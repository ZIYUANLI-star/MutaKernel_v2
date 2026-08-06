"""21:39 check: health + progress since 17:24 (was 8662 rows) + blueprint fit."""
import _remote as R

OUT = "/root/mk_v2_runs/e3_campaign"
c = R.connect()

print("### A. processes + GPU + git + markers + guard")
R.run(c, "pgrep -af 'orchestrator|run_fse_experiment|guard_lane_m' | grep -v grep | wc -l; "
         "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader; "
         "cd /root/mk_v2 && git status --porcelain | wc -l; "
         "ls " + OUT + "/ | grep -i 'DONE\\|BLOCKED' || echo no_markers; "
         "tail -1 " + OUT + "/guard_lane_m.log", timeout=60)

print("### B. progress + strategy-level tallies (Table 7 shape)")
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json, collections, statistics\n"
         "OUT='" + OUT + "/lane_m_run'\n"
         "manifest=json.load(open(OUT+'/run_manifest.json'))['manifest_sha256']\n"
         "rows=[json.loads(l) for l in open(OUT+'/observations.jsonl') if l.strip()]\n"
         "post=[r for r in rows if r['run_manifest_sha256']==manifest]\n"
         "print('total rows:', len(rows), '| post-fix rows:', len(post))\n"
         "st=collections.Counter(r['validation_status'] for r in post)\n"
         "print('post-fix statuses:', dict(st))\n"
         "w=sorted(r['parent_wall_ms']/1000 for r in post[-300:])\n"
         "print('recent-300 wall: median', round(w[len(w)//2],1), 's mean',\n"
         "      round(statistics.mean(w),1), 's p90', round(w[9*len(w)//10],1), 's')\n"
         "# whole-ledger detection tallies by strategy (Table 6b/7 shape check)\n"
         "det=collections.defaultdict(set)\n"
         "for r in rows:\n"
         "    if r['validation_status']=='fail':\n"
         "        det[r['strategy_name']].add(r['subject_id'])\n"
         "print('whole-ledger detected subjects by strategy:')\n"
         "for s in sorted(det): print(' ', s, len(det[s]))\n"
         "allf={x for v in det.values() for x in v}\n"
         "print('union detected subjects:', len(allf), '/653')\n"
         "EOF", timeout=300)

print("### C. 60s throughput")
R.run(c, f"a=$(wc -l < {OUT}/lane_m_run/observations.jsonl); sleep 60; "
         f"b=$(wc -l < {OUT}/lane_m_run/observations.jsonl); echo delta_60s=$((b-a))", timeout=130)
c.close()
print("CHECK2139_DONE")
