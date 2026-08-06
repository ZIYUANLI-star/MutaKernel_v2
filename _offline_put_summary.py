"""Mirror the interim summary md to /root/mk_v2_runs/e1/analysis/."""
from _remote import connect

client = connect()
sftp = client.open_sftp()
sftp.put(
    "MutakernelV2/实验/重跑实验数据/离线分析/离线复用分析_汇总.md",
    "/root/mk_v2_runs/e1/analysis/offline_reuse_summary_interim.md")
sftp.close()
client.close()
print("PUT_SUMMARY_DONE")
