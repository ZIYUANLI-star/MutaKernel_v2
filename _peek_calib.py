import _remote as R

c = R.connect()
R.run(c, "ls /root/mk_v2_runs/e3_b9_calib/ | head -20", timeout=60)
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json, glob\n"
         "fs = sorted(glob.glob('/root/mk_v2_runs/e3_b9_calib/*.json'))\n"
         "print('json files:', len(fs))\n"
         "for f in fs[:3]:\n"
         "    j = json.load(open(f))\n"
         "    print('---', f.split('/')[-1], 'keys:', list(j.keys())[:12])\n"
         "s = json.load(open('/root/mk_v2_runs/e3_b9_calib/b9_calib_final_summary.json'))\n"
         "print('summary keys:', list(s.keys()))\n"
         "print('calibrated_total:', s.get('calibrated_total'))\n"
         "# look for a per-unit ledger with tolerances\n"
         "import os\n"
         "for f in fs:\n"
         "    j = json.load(open(f))\n"
         "    if isinstance(j, dict) and any('tol' in str(k).lower() for k in j.keys()):\n"
         "        print('tol-carrier:', f.split('/')[-1], list(j.keys())[:8]); break\n"
         "EOF", timeout=120)
c.close()
print("DONE")
