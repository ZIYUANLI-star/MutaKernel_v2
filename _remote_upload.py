"""Upload local files to remote via paramiko SFTP."""
import sys
import _remote

pairs = [
    # (local, remote)
    ("_p53_polybench_remote.py", "/root/mk_v2/_p53_polybench_remote.py"),
]
c = _remote.connect()
sftp = c.open_sftp()
for local, remote in pairs:
    sftp.put(local, remote)
    print("uploaded", local, "->", remote)
sftp.close()
c.close()
