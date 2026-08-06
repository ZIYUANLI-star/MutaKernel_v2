"""17:21 routine check: health, progress since 12:04 (was 7254 rows)."""
import _remote as R

OUT = "/root/mk_v2_runs/e3_campaign"
c = R.connect()

print("### A. processes + GPU + git + markers")
R.run(c, "pgrep -af 'orchestrator|run_fse_experiment|guard_lane_m' | grep -v grep | wc -l; "
         "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader; "
         "cd /root/mk_v2 && git status --porcelain | wc -l; "
         "ls " + OUT + "/ | grep -i 'DONE\\|BLOCKED' || echo no_markers; "
         "tail -1 " + OUT + "/guard_lane_m.log", timeout=60)

print("### B. progress since 12:04")
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
         "print('post-fix distinct subjects:', len(subs), '/653')\n"
         "w=sorted(r['parent_wall_ms']/1000 for r in post[-200:])\n"
         "print('recent-200 wall: median', round(w[len(w)//2],1), 's mean',\n"
         "      round(statistics.mean(w),1), 's p90', round(w[9*len(w)//10],1), 's')\n"
         "fails=[r for r in post if r['validation_status']=='fail']\n"
         "print('post-fix FAILs:', len(fails), 'on', len({r['subject_id'] for r in fails}), 'subjects')\n"
         "EOF", timeout=300)

print("### C. 3-min throughput")
R.run(c, f"a=$(wc -l < {OUT}/lane_m_run/observations.jsonl); sleep 180; "
         f"b=$(wc -l < {OUT}/lane_m_run/observations.jsonl); echo delta_3min=$((b-a))", timeout=250)
c.close()
print("CHECK1721_DONE")
