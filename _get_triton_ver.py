import _remote
c = _remote.connect()
_, o, _ = _remote.run(c, "/root/miniconda3/bin/python -c 'import triton; print(\"TRITON\", triton.__version__)'", timeout=90, echo=False)
c.close()
print(o)
