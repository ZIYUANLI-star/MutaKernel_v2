import _remote, os

c = _remote.connect()
sftp = c.open_sftp()
os.makedirs("_wc_local", exist_ok=True)
for f in ["_wc_audit.py", "_wc_start.py", "_wc_analyze.py"]:
    sftp.get("/root/mk_v2/" + f, "_wc_local/" + f)
    print("got", f)
R = "/root/mk_v2_runs/e1/witness_confirmation"
for f in ["audit.log", "audit_lane0.log", "audit_lane1.log", "lane0_stdout.log",
          "lane1_stdout.log", "starter.log", "starter_stdout.log", "control_stdout.log"]:
    try:
        sftp.get(R + "/" + f, "_wc_local/" + f)
        print("got", f)
    except Exception as e:
        print("skip", f, e)
sftp.close()
c.close()
print("DONE_FETCH")
