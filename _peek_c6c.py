import _remote as R

c = R.connect()
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "d = '/root/mk_v2/external/C6_gpuemu/gpuemu-corpus/gpuemu_corpus/data'\n"
         "src = open(d + '/gelu_triton/kernel.py').read()\n"
         "print(src[-1800:])\n"
         "EOF", timeout=60)
R.run(c, "grep -n 'def \\|^class ' /root/mk_v2/external/C6_gpuemu/gpuemu-corpus/gpuemu_corpus/data/*/kernel.py | grep -v 'def _' | head -40", timeout=60)
c.close()
print("DONE")
