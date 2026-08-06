import _remote as R

c = R.connect()
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json\n"
         "s = json.load(open('/root/mk_v2_runs/e3_b9_calib/b9_calib_final_summary.json'))\n"
         "print(json.dumps({k: s[k] for k in s if k != 'unresolved_units'}, default=str)[:1200])\n"
         "print('dedup_rule:', s.get('dedup_rule'))\n"
         "EOF", timeout=60)
R.run(c, "ls /root/mk_v2_runs/e3_b9_calib/archive/ 2>/dev/null | head; "
         "find /root/mk_v2_runs -maxdepth 2 -name '*calib*' -newer /root/mk_v2_runs/e3_b9_calib/calibration_lane0.jsonl 2>/dev/null | head -20", timeout=60)
c.close()
print("DONE")
