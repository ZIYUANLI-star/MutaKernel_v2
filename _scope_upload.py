"""Upload the frozen campaign scope manifest to the remote campaign dir."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put(r"MutakernelV2\实验\补充实验数据\e3_campaign_scope_v1.json",
         "/root/mk_v2_runs/e3_campaign/e3_campaign_scope_v1.json")
sftp.close()
_, o, _ = _remote.run(c, (
    "md5sum /root/mk_v2_runs/e3_campaign/e3_campaign_scope_v1.json; "
    "/root/miniconda3/bin/python -c \"import json; "
    "m=json.load(open('/root/mk_v2_runs/e3_campaign/e3_campaign_scope_v1.json')); "
    "print(m['counts'])\""), timeout=60, echo=False)
print(o)
c.close()
