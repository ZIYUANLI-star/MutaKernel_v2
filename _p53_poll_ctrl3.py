import _remote
c = _remote.connect()
_remote.run(c, "ps -eo pid,etime,cmd | grep -E '_p53_control3|_inner_one' | grep -v grep", timeout=30)
print("---LOG---")
_remote.run(c, "cat /root/mk_v2_runs/e1/_p53_control3.log", timeout=30)
c.close()
