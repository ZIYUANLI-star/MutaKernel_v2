import _remote as R

c = R.connect()
R.run(c, "ls /root/mk_v2/external/C6_gpuemu/ 2>/dev/null; "
         "find /root/mk_v2/external -maxdepth 4 -name 'data' -type d 2>/dev/null; "
         "ls /root/mk_v2_runs/e3_c6/ 2>/dev/null", timeout=60)
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json, glob, os\n"
         "hits = glob.glob('/root/mk_v2/external/**/gpuemu_corpus/data', recursive=True)\n"
         "print('data dirs:', hits)\n"
         "if hits:\n"
         "    d = hits[0]\n"
         "    ops = sorted(os.listdir(d))\n"
         "    print('ops:', len(ops), ops[:8])\n"
         "    op = ops[0]\n"
         "    meta = json.load(open(os.path.join(d, op, 'meta.json')))\n"
         "    print('meta:', json.dumps(meta)[:800])\n"
         "    ref = open(os.path.join(d, op, 'ref_fp64.py')).read()\n"
         "    print('--- ref head ---')\n"
         "    print(ref[:900])\n"
         "    k = open(os.path.join(d, op, 'kernel.py')).read()\n"
         "    print('--- kernel head ---')\n"
         "    print(k[:900])\n"
         "EOF", timeout=120)
c.close()
print("DONE")
