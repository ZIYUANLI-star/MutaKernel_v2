import _remote as R

c = R.connect()
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json, os\n"
         "d = '/root/mk_v2/external/C6_gpuemu/gpuemu-corpus/gpuemu_corpus/data'\n"
         "ops = sorted(o for o in os.listdir(d) if os.path.isdir(os.path.join(d, o)))\n"
         "print('op dirs:', len(ops))\n"
         "op = 'gelu_triton'\n"
         "meta = json.load(open(os.path.join(d, op, 'meta.json')))\n"
         "print('meta:', json.dumps(meta, indent=1)[:1000])\n"
         "print('files:', os.listdir(os.path.join(d, op)))\n"
         "print('--- ref_fp64.py ---')\n"
         "print(open(os.path.join(d, op, 'ref_fp64.py')).read()[:1200])\n"
         "print('--- kernel.py head ---')\n"
         "print(open(os.path.join(d, op, 'kernel.py')).read()[:1200])\n"
         "print('--- _refkit.py head ---')\n"
         "print(open(os.path.join(d, '_refkit.py')).read()[:800])\n"
         "EOF", timeout=120)
c.close()
print("DONE")
