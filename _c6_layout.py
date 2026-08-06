import _remote as R

c = R.connect()
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json, os\n"
         "D = '/root/mk_v2/external/C6_gpuemu/gpuemu-corpus/gpuemu_corpus/data'\n"
         "for op in sorted(os.listdir(D)):\n"
         "    p = os.path.join(D, op)\n"
         "    if not os.path.isdir(p):\n"
         "        continue\n"
         "    files = sorted(os.listdir(p))\n"
         "    print(op, '->', files)\n"
         "print()\n"
         "m = json.load(open(D + '/gelu_triton_buggy/meta.json'))\n"
         "print('buggy meta keys:', sorted(m.keys()))\n"
         "for k in ('base_op', 'ref', 'reference', 'baseline_op', 'parent'):\n"
         "    if k in m:\n"
         "        print(k, '=', m[k])\n"
         "print(json.dumps(m, indent=1)[:1200])\n"
         "EOF", timeout=60)
c.close()
print("DONE")
