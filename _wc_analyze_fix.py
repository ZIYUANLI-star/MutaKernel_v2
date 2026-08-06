"""Patch the NoneType bug in remote _wc_analyze.py, then run it."""
import _remote

OLD = '"max_abs_error": (rec or {}).get("divergence", {}).get("oracle", {}) and None,'
NEW = '"max_abs_error": ((rec or {}).get("divergence") or {}).get("oracle") and None,'

c = _remote.connect()
s = c.open_sftp()
path = "/root/mk_v2/_wc_analyze.py"
text = s.open(path).read().decode()
assert OLD in text, "anchor missing"
text = text.replace(OLD, NEW)
with s.open(path, "w") as f:
    f.write(text)
s.close()
print("patched")
_, o, _ = _remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _wc_analyze.py 2>&1 | tail -120",
                      timeout=300, echo=False)
c.close()
print(o)
print("ANALYZE_DONE")
