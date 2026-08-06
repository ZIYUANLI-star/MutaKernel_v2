"""22:38 routine check: health, progress, new data, throughput trend."""
import _remote as R

OUT = "/root/mk_v2_runs/e3_campaign"
c = R.connect()

print("### A. processes + GPU + git")
R.run(c, "pgrep -af 'orchestrator|run_fse_experiment|guard_lane_m' | grep -v pgrep; "
         "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader; "
         "cd /root/mk_v2 && git status --porcelain | wc -l", timeout=60)

print("### B. progress since 19:57 (was 4799)")
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
         "print('post-fix distinct subjects:', len(subs))\n"
         "walls=sorted(r['parent_wall_ms']/1000 for r in post)\n"
         "n=len(walls)\n"
         "print('post-fix wall: median', round(walls[n//2],1), 's p90', round(walls[9*n//10],1),\n"
         "      's mean', round(statistics.mean(walls),1), 's')\n"
         "# recent 100 rows only (steady-state estimate)\n"
         "w2=sorted(r['parent_wall_ms']/1000 for r in post[-100:])\n"
         "print('recent-100 wall: median', round(w2[len(w2)//2],1), 's mean', round(statistics.mean(w2),1), 's')\n"
         "fails=[r for r in post if r['validation_status']=='fail']\n"
         "print('post-fix FAILs:', len(fails), 'subjects:', len({r['subject_id'] for r in fails}))\n"
         "EOF", timeout=300)

print("### C. instantaneous throughput (3 min)")
R.run(c, f"a=$(wc -l < {OUT}/lane_m_run/observations.jsonl); sleep 180; "
         f"b=$(wc -l < {OUT}/lane_m_run/observations.jsonl); "
         f"echo now=$b delta_3min=$((b-a))", timeout=250)

print("### D. errors/restarts since 18:01?")
R.run(c, f"tail -2 {OUT}/lane_m_run.log; tail -2 {OUT}/guard_lane_m.log; "
         f"ls {OUT}/ | grep -i 'DONE\\|BLOCKED' || echo no_markers", timeout=60)
c.close()
print("CHECK2238_DONE")
