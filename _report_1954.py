"""19:54 comprehensive check: new data, correctness, throughput, expectations."""
import _remote as R

OUT = "/root/mk_v2_runs/e3_campaign"
c = R.connect()

print("### A. processes + GPU + git")
R.run(c, "pgrep -af 'orchestrator|run_fse_experiment|guard_lane_m' | grep -v pgrep | wc -l; "
         "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader; "
         "cd /root/mk_v2 && git status --porcelain | wc -l", timeout=60)

print("### B. ledger size + throughput trend since cache fix")
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json, time, collections, statistics\n"
         "OUT='" + OUT + "/lane_m_run'\n"
         "manifest=json.load(open(OUT+'/run_manifest.json'))['manifest_sha256']\n"
         "rows=[json.loads(l) for l in open(OUT+'/observations.jsonl') if l.strip()]\n"
         "post=[r for r in rows if r['run_manifest_sha256']==manifest]\n"
         "print('total rows:', len(rows), '| rows under cache-fix manifest:', len(post))\n"
         "walls=[r['parent_wall_ms']/1000 for r in post]\n"
         "print('post-fix wall: median', round(statistics.median(walls),1),\n"
         "      's mean', round(statistics.mean(walls),1), 's sum_h', round(sum(walls)/3600,2))\n"
         "st=collections.Counter(r['validation_status'] for r in post)\n"
         "print('post-fix statuses:', dict(st))\n"
         "subs=collections.Counter(r['subject_id'] for r in post)\n"
         "print('post-fix distinct subjects:', len(subs))\n"
         "strat=collections.Counter((r['strategy_name'],r['validation_status']) for r in post)\n"
         "agg=collections.defaultdict(dict)\n"
         "for (s,v),n in strat.items(): agg[s][v]=n\n"
         "for s in sorted(agg): print(' ', s, dict(agg[s]))\n"
         "EOF", timeout=300)

print("### C. instantaneous throughput (3 min)")
R.run(c, f"a=$(wc -l < {OUT}/lane_m_run/observations.jsonl); sleep 180; "
         f"b=$(wc -l < {OUT}/lane_m_run/observations.jsonl); "
         f"echo now=$b delta_3min=$((b-a))", timeout=250)

print("### D. any FAIL rows so far (whole ledger) - the RQ1 signal")
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json, collections\n"
         "OUT='" + OUT + "/lane_m_run'\n"
         "rows=[json.loads(l) for l in open(OUT+'/observations.jsonl') if l.strip()]\n"
         "st=collections.Counter(r['validation_status'] for r in rows)\n"
         "print('whole-ledger statuses:', dict(st))\n"
         "fails=[r for r in rows if r['validation_status']=='fail']\n"
         "print('FAIL rows:', len(fails), 'distinct subjects:', len({r['subject_id'] for r in fails}))\n"
         "bycorp=collections.Counter(r['subject_id'].split('__')[0] for r in fails)\n"
         "print('FAIL by corpus:', dict(bycorp))\n"
         "bystrat=collections.Counter(r['strategy_name'] for r in fails)\n"
         "print('FAIL by strategy:', dict(bystrat))\n"
         "inc=[r for r in rows if r['validation_status']=='inconclusive']\n"
         "reasons=collections.Counter()\n"
         "for r in inc:\n"
         "    errs=(r.get('worker_result') or {}).get('errors') or []\n"
         "    reasons[errs[0]['exception_type'] if errs else 'unknown']+=1\n"
         "print('inconclusive by exception:', dict(reasons))\n"
         "EOF", timeout=300)
c.close()
print("REPORT_PROBE_DONE")
