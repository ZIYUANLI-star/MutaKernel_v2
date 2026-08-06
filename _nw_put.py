"""Upload the review orchestrator to the remote box."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_nw_review.py", "/root/mk_v2/_p37_newwitness_review.py")
print("uploaded", sftp.stat("/root/mk_v2/_p37_newwitness_review.py").st_size)
sftp.close()
_remote.run(c, "md5sum /root/mk_v2/_p37_newwitness_review.py")
c.close()
