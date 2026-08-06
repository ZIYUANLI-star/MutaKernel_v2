import json
import _remote as R

c = R.connect()
print("### worker invocation block")
R.run(c, "sed -n '150,240p' /root/mk_v2/_b9_calib_driver_v2.py", timeout=60)
print("### CRITICAL_PATH_NEEDLE and consts")
R.run(c, "sed -n '1,60p' /root/mk_v2/_b9_calib_driver_v2.py", timeout=60)
print("### one existing unit from wave-1 queue")
code, o, _ = R.run(c, "python3 - <<'EOF'\n"
                      "import json\n"
                      "s=json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json'))\n"
                      "k=sorted(s['units'])[0]\n"
                      "print(json.dumps(s['units'][k], indent=1))\n"
                      "print('top keys:', sorted(s.keys()))\n"
                      "EOF", timeout=60)
print("### L3 signed contract sample fields")
R.run(c, "head -c 1200 /root/mk_v2_runs/e2_reconcile/contracts_l3_signed_v2.jsonl", timeout=60)
c.close()
print("DONE")
