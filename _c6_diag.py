import _remote as R

c = R.connect()
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json\n"
         "from collections import Counter\n"
         "reasons = Counter()\n"
         "for l in open('/root/mk_v2_runs/e3_campaign/wave15/_smoke/c6/gelu_buggy_mfull.jsonl'):\n"
         "    r = json.loads(l)\n"
         "    reasons[(r.get('reason') or '')[:200]] += 1\n"
         "for k, v in reasons.most_common(5):\n"
         "    print(v, '|', k)\n"
         "EOF", timeout=60)
c.close()
print("DONE")
