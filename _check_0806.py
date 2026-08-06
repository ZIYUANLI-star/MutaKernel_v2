"""Aug 6 11:36 check: health, overnight progress, throughput, sweep status."""
import _remote as R

OUT = "/root/mk_v2_runs/e3_campaign"
c = R.connect()

print("### A. processes + GPU + git + markers")
R.run(c, "pgrep -af 'orchestrator|run_fse_experiment|guard_lane_m' | grep -v pgrep; "
         "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader; "
         "cd /root/mk_v2 && git status --porcelain | wc -l; "
         "ls " + OUT + "/ | grep -i 'DONE\\|BLOCKED' || echo no_markers", timeout=60)

print("### B. overnight progress (was 5062 at 22:41)")
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json, collections, statistics\n"
         "OUT='" + OUT + "/lane_m_run'\n"
         "manifest=json.load(open(OUT+'/run_manifest.json'))['manifest_sha256']\n"
         "rows=[json.loads(l) for l in open(OUT+'/observations.jsonl') if l.strip()]\n"
         "post=[r for r in rows if r['run_manifest_sha256']==manifest]\n"
         "print('total rows:', len(rows), '| post-fix rows:', len(post))\n"
         "st=collections.Counter(r['validation_status'] for r in post)\n"
         "print('post-fix statuses:', dict(st))\n"
         "subs={r['subject_id'] for r in post}\n"
         "print('post-fix distinct subjects:', len(subs), '/ 653')\n"
         "w=sorted(r['parent_wall_ms']/1000 for r in post[-300:])\n"
         "print('recent-300 wall: median', round(w[len(w)//2],1), 's mean',\n"
         "      round(statistics.mean(w),1), 's p90', round(w[9*len(w)//10],1), 's')\n"
         "fails=[r for r in post if r['validation_status']=='fail']\n"
         "print('post-fix FAILs:', len(fails), 'subjects:', len({r['subject_id'] for r in fails}))\n"
         "inc=[r for r in post if r['validation_status']=='inconclusive']\n"
         "reasons=collections.Counter()\n"
         "for r in inc:\n"
         "    errs=(r.get('worker_result') or {}).get('errors') or []\n"
         "    reasons[errs[0]['exception_type'] if errs else 'unknown']+=1\n"
         "print('post-fix inconclusive types:', dict(reasons))\n"
         "EOF", timeout=300)

print("### C. instantaneous throughput (3 min)")
R.run(c, f"a=$(wc -l < {OUT}/lane_m_run/observations.jsonl); sleep 180; "
         f"b=$(wc -l < {OUT}/lane_m_run/observations.jsonl); "
         f"echo now=$b delta_3min=$((b-a))", timeout=250)

print("### D. restarts/errors overnight?")
R.run(c, f"tail -2 {OUT}/lane_m_run.log; tail -2 {OUT}/guard_lane_m.log", timeout=60)
c.close()
print("CHECK0806_DONE")
