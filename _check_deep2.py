"""Decisive: fraction of recent worker logs that ran a fresh compile."""
import _remote as R

c = R.connect()
R.run(c, "cd /root/mk_v2_runs/e3_campaign/lane_m_run/worker_logs && "
         "recent=$(ls -t | head -40) && "
         "build=0; nolog=0; total=0; "
         "for f in $recent; do total=$((total+1)); "
         "if grep -q 'Building extension module' $f 2>/dev/null; then build=$((build+1)); fi; "
         "if [ ! -s $f ]; then nolog=$((nolog+1)); fi; done; "
         "echo recent=$total fresh_compiles=$build empty_logs=$nolog", timeout=120)
print("### recent subjects sequence (are we revisiting or first-visiting?)")
R.run(c, "tail -60 /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl | "
         "/root/miniconda3/bin/python -c \"import sys,json\n"
         "seen=[]\n"
         "for l in sys.stdin:\n"
         "    r=json.loads(l); s=r['subject_id']\n"
         "    if not seen or seen[-1]!=s: seen.append(s)\n"
         "print(len(seen),'subject switches in last 60 rows')\n"
         "for s in seen[-12:]: print(' ', s)\"", timeout=60)
print("### distinct subjects in v2 rows only (post early-stop restart)")
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json\n"
         "run_ids=set(); subs=set(); n=0\n"
         "for l in open('/root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl'):\n"
         "    if not l.strip(): continue\n"
         "    r=json.loads(l); n+=1\n"
         "    run_ids.add(r.get('run_manifest_sha256','')[:8])\n"
         "    subs.add(r['subject_id'])\n"
         "print('rows',n,'runs',run_ids,'distinct subjects',len(subs))\n"
         "EOF", timeout=300)
c.close()
print("DEEP2_DONE")
