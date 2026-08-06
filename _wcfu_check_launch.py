import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, "pgrep -af _wcfu_chain.py; echo MARK; "
                         "tail -n 10 /root/mk_v2_runs/e3_b9_calib/wcfu_chain.log 2>/dev/null; echo MARK; "
                         "tail -n 5 /root/mk_v2_runs/e3_b9_calib/wcfu_chain_stdout.log 2>/dev/null",
                      timeout=30, echo=False)
c.close()
print(o)
print("CHECK_DONE")
