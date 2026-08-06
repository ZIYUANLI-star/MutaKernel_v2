"""Audit probe 5: manifest structure + verify call sites."""
import _remote as R

c = R.connect()
print("### manifest top structure + one subject")
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json\n"
         "m=json.load(open('/root/mk_v2_runs/e3_campaign/wave2_subject_manifest.json'))\n"
         "print('top keys:', list(m.keys()) if isinstance(m,dict) else type(m))\n"
         "subs=m.get('subjects') if isinstance(m,dict) else m\n"
         "print(json.dumps(subs[0], indent=1)[:1500])\n"
         "import re\n"
         "t=json.dumps(subs)\n"
         "hits=sorted(set(re.findall(r'[\\w/.-]*C5_kernelbench_samples_wave2[\\w/.-]*', t)))\n"
         "print('C5 wave2 path refs:', len(hits))\n"
         "for h in hits[:3]: print(' ', h)\n"
         "EOF", timeout=120)
print("### verify_live_environment call sites")
R.run(c, "grep -n '_verify_live_environment\\|_capture_live_environment' /root/mk_v2/scripts/run_fse_experiment.py", timeout=60)
R.run(c, "sed -n '91,120p' /root/mk_v2/scripts/run_fse_experiment.py", timeout=60)
c.close()
print("AUDIT5_DONE")
