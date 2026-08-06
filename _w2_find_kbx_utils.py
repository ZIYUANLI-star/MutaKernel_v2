import _remote as R

c = R.connect()
R.run(c, "find /root/KernelBenchX_hf /root/KernelBenchX_data -name 'data_utils.py' "
         "2>/dev/null; ls /root/KernelBenchX_hf/kernelbenchx/ | head; "
         "find /root/KernelBenchX_hf -maxdepth 2 -name 'utils' -type d", timeout=60)
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json, re\n"
         "n_ok = 0; n = 0\n"
         "with open('/root/KernelBenchX_hf/kbx_corpus/all_records.jsonl') as fh:\n"
         "    for l in fh:\n"
         "        r = json.loads(l)\n"
         "        n += 1\n"
         "        for side in ('before', 'after'):\n"
         "            m = re.search(r\"'exe_ok': (True|False)\", r[side])\n"
         "            assert m, side\n"
         "        n_ok += 1\n"
         "print('records', n, 'parse ok', n_ok)\n"
         "EOF", timeout=60)
c.close()
print("DONE")
