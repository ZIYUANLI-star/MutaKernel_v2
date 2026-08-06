"""Deploy the chain trigger and verify its read-only logic (no launch yet)."""
import io

import _remote

TEST = r'''
import sys
sys.path.insert(0, "/root/mk_v2")
import _b9_chain_trigger as t

print("== SIGNOFF_DONE present:", t.SIGNOFF_DONE.is_file())
print("== FIRED present:", t.FIRED.is_file())
print("== pause marker present:", t.PAUSE_MARKER.is_file())
print("== critical path processes:")
for needle, pid, cl in t.critical_path_processes():
    print("   %-24s pid=%-7d %s" % (needle, pid, cl[:110]))
print("== b9 processes:", t.b9_processes())
print("== gpu compute apps:", t.gpu_compute_apps())
print("== start_blockers (expect non-empty right now):")
for r in t.start_blockers():
    print("   -", r[:160])
units = t.requeue_wave_units()
print("== requeue wave: %d units" % len(units))
print("  ", units)
print("== lanes_done:", t.lanes_done())
print("SELFTEST_OK")
'''

c = _remote.connect()
sftp = c.open_sftp()
with open("_b9_chain_trigger.py", "rb") as fh:
    sftp.putfo(fh, "/root/mk_v2/_b9_chain_trigger.py")
sftp.putfo(io.BytesIO(TEST.encode()), "/root/_h8_test.py")
sftp.close()

for cmd in [
    "cd /root/mk_v2 && /root/miniconda3/bin/python -m py_compile _b9_chain_trigger.py && echo COMPILE_OK",
    "md5sum /root/mk_v2/_b9_chain_trigger.py",
    "/root/miniconda3/bin/python /root/_h8_test.py",
    "echo '===== signoff orch DONE marker semantics'; grep -n 'SIGNOFF_ORCH_DONE\\|DONE\\|def main\\|rounds\\|MAX_ROUND' /root/mk_v2/_signoff_orch.py | head -40",
]:
    print("\n#### " + cmd[:80])
    _remote.run(c, cmd, timeout=300)
c.close()
print("\nH8_DONE")
