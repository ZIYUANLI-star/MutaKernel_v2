"""Round 1 driver: push the read-only inventory script to the A800, run it,
and fetch the JSON report back to _inc_inventory_report.json locally."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_inc_inventory_remote.py", "/root/mk_v2/_inc_inventory_remote.py")
print("PUT _inc_inventory_remote.py")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python "
               "_inc_inventory_remote.py", timeout=300)
sftp.get("/root/mk_v2_runs/e1/_inc_inventory_report.json",
         "_inc_inventory_report.json")
print("GOT _inc_inventory_report.json")
sftp.close()
c.close()
print("AUDIT1_DONE")
