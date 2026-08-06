"""Where do the 20-40s go on slow repeat rows? timings_ms breakdown."""
import _remote as R

OUT = "/root/mk_v2_runs/e3_campaign"
c = R.connect()
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json\n"
         "OUT='" + OUT + "/lane_m_run'\n"
         "manifest=json.load(open(OUT+'/run_manifest.json'))['manifest_sha256']\n"
         "rows=[json.loads(l) for l in open(OUT+'/observations.jsonl') if l.strip()]\n"
         "post=[r for r in rows if r['run_manifest_sha256']==manifest]\n"
         "seen=set()\n"
         "for r in post:\n"
         "    s=r['subject_id']; rep=s in seen; seen.add(s)\n"
         "    if rep and r['parent_wall_ms']>20000:\n"
         "        w=r.get('worker_result') or {}\n"
         "        print(r['subject_id'][:40], r['strategy_name'], round(r['parent_wall_ms']/1000,1),'s')\n"
         "        print('  timings_ms:', json.dumps(w.get('timings_ms'))[:500])\n"
         "        print('  case params:', json.dumps(r.get('parameters'))[:300])\n"
         "        break\n"
         "# and a fast one for contrast\n"
         "seen=set()\n"
         "for r in post:\n"
         "    s=r['subject_id']; rep=s in seen; seen.add(s)\n"
         "    if rep and r['parent_wall_ms']<5000:\n"
         "        w=r.get('worker_result') or {}\n"
         "        print('FAST', r['subject_id'][:40], r['strategy_name'], round(r['parent_wall_ms']/1000,1),'s')\n"
         "        print('  timings_ms:', json.dumps(w.get('timings_ms'))[:500])\n"
         "        break\n"
         "EOF", timeout=300)
c.close()
print("RECHECK3_DONE")
