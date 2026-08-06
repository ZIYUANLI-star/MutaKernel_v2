"""Audit probe 4: wave2 manifest C5 paths + env validation timing."""
import _remote as R

c = R.connect()
print("### wave2 manifest C5 artifact paths (sample)")
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json\n"
         "m=json.load(open('/root/mk_v2_runs/e3_campaign/wave2_subject_manifest.json'))\n"
         "subs=m['subjects'] if isinstance(m,dict) and 'subjects' in m else m\n"
         "c5=[s for s in subs if 'C5' in json.dumps(s)[:200]][:2]\n"
         "for s in c5:\n"
         "    print(json.dumps(s, indent=1)[:900])\n"
         "print('total subjects:', len(subs))\n"
         "paths=set()\n"
         "for s in subs:\n"
         "    t=json.dumps(s)\n"
         "    import re\n"
         "    for p in re.findall(r'\"(/root/[^\"]+|external/[^\"]+)\"', t):\n"
         "        paths.add(p.split('/C5_kernelbench_samples_wave2')[0] if 'C5_kernelbench_samples_wave2' in p else p.rsplit('/',1)[0])\n"
         "for p in sorted(paths)[:15]: print('ROOT:', p)\n"
         "EOF", timeout=120)
print("### env validation timing in runner")
R.run(c, "grep -n 'differs from the captured\\|validate_environment\\|def .*environment' /root/mk_v2/scripts/run_fse_experiment.py /root/mk_v2/src/experiments/*.py 2>/dev/null | head -15", timeout=60)
c.close()
print("AUDIT4_DONE")
