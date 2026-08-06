"""Deploy + run the P37 field fix / P95 verification remotely."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_p37_field_fix.py", "/root/mk_v2/_p37_field_fix.py")
sftp.close()
_, o, e = _remote.run(
    c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _p37_field_fix.py",
    timeout=300, echo=False)
print(o)
if e.strip():
    print("STDERR:\n" + e[-2000:])
c.close()
