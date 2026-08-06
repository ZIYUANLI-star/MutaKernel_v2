import _remote

c = _remote.connect()
base = "/root/mk_v2/external/C6_gpuemu/gpuemu-corpus/gpuemu_corpus/data"
CMDS = [
    "ls %s | head -30" % base,
    "sed -n '1,60p' %s/elu_triton/kernel.py" % base,
    "sed -n '1,40p' %s/elu_triton/ref_fp64.py" % base,
    "ls %s/elu_triton/" % base,
    "cat %s/elu_triton/meta.json 2>/dev/null" % base,
]
for cmd in CMDS:
    _, o, e = _remote.run(c, cmd, timeout=60, echo=False)
    print(o)
    print('=====')
c.close()
print('DONE')
