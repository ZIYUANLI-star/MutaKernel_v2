"""Check for residual redundant compilation after the namespace fix."""
import _remote as R

OUT = "/root/mk_v2_runs/e3_campaign"
c = R.connect()

print("### throughput over 4 minutes + row wall stats since fix (18:01)")
R.run(c, f"a=$(wc -l < {OUT}/lane_m_run/observations.jsonl); sleep 240; "
         f"b=$(wc -l < {OUT}/lane_m_run/observations.jsonl); "
         f"echo rows=$b delta_4min=$((b-a))", timeout=330)

print("### per-subject cache behavior since fix: repeat rows should have no build")
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json, collections\n"
         "rows=[]\n"
         "for l in open('" + OUT + "/lane_m_run/observations.jsonl'):\n"
         "    if l.strip(): rows.append(json.loads(l))\n"
         "post=[r for r in rows if r.get('run_manifest_sha256')]\n"
         "manifest=json.load(open('" + OUT + "/lane_m_run/run_manifest.json'))\n"
         "cur=manifest['manifest_sha256']\n"
         "post=[r for r in rows if r['run_manifest_sha256']==cur]\n"
         "print('rows under cache-fix manifest:', len(post))\n"
         "bysub=collections.Counter(r['subject_id'] for r in post)\n"
         "walls=collections.defaultdict(list)\n"
         "for r in post: walls[r['subject_id']].append(r['parent_wall_ms']/1000)\n"
         "slow_repeats=0; checked=0\n"
         "for s, ws in walls.items():\n"
         "    for w in ws[1:]:\n"
         "        checked+=1\n"
         "        if w>20: slow_repeats+=1\n"
         "first=[ws[0] for ws in walls.values()]\n"
         "rep=[w for ws in walls.values() for w in ws[1:]]\n"
         "import statistics\n"
         "if first: print('first-row wall: median', round(statistics.median(first),1),'s n',len(first))\n"
         "if rep: print('repeat-row wall: median', round(statistics.median(rep),1),'s n',len(rep), ' >20s count:', slow_repeats)\n"
         "EOF", timeout=300)

print("### do repeat-row worker logs still build?")
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json, collections, os\n"
         "OUT='" + OUT + "/lane_m_run'\n"
         "manifest=json.load(open(OUT+'/run_manifest.json'))['manifest_sha256']\n"
         "rows=[json.loads(l) for l in open(OUT+'/observations.jsonl') if l.strip()]\n"
         "post=[r for r in rows if r['run_manifest_sha256']==manifest]\n"
         "seen=set(); results=collections.Counter()\n"
         "for r in post:\n"
         "    s=r['subject_id']\n"
         "    repeat = s in seen\n"
         "    seen.add(s)\n"
         "    wl=(r.get('worker_result') or {}).get('evidence',{}).get('worker_log',{}).get('logical_path')\n"
         "    if not wl: continue\n"
         "    p=os.path.join(OUT, wl.split('/',0)[0]) if False else os.path.join(OUT, wl)\n"
         "    try: txt=open(p, errors='replace').read()\n"
         "    except Exception: continue\n"
         "    built='Building extension module' in txt\n"
         "    results[(repeat, built)]+=1\n"
         "print('(is_repeat_row, did_build): count')\n"
         "for k,v in sorted(results.items()): print(' ',k,v)\n"
         "EOF", timeout=300)
c.close()
print("RECHECK_DONE")
