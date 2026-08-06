"""Pull audit-relevant Lane M logs to local (excludes compile artifacts)."""
import os
import _remote as R

c = R.connect()
print("### pack audit-relevant logs on remote")
R.run(c, "cd /root/mk_v2_runs/e3_campaign && "
         "tar czf /root/lane_m_audit_logs_$(date +%Y%m%d_%H%M).tar.gz "
         "lane_m_run/observations.jsonl lane_m_run/worker_logs "
         "lane_m_run/run_manifest.json lane_m_run/run_manifest_v1_pre_earlystop.json "
         "lane_m_run.log guard_lane_m.log wave1_environment.json "
         "wave1_environment_v2.json wave1_lane_m_plan_v2.json "
         "wave1_subject_manifest_v2.json 2>&1 | tail -2; "
         "ls -la /root/lane_m_audit_logs_*.tar.gz | tail -1", timeout=600)
_, o, _ = R.run(c, "ls -t /root/lane_m_audit_logs_*.tar.gz | head -1",
                timeout=30, echo=False)
remote_tar = o.strip()
print("remote tar:", remote_tar)
R.run(c, f"md5sum {remote_tar}", timeout=120)

local_dir = r"MutakernelV2\实验\补充实验数据\lane_m_盲审日志备份"
os.makedirs(local_dir, exist_ok=True)
local_path = os.path.join(local_dir, os.path.basename(remote_tar))
sftp = c.open_sftp()
sftp.get(remote_tar, local_path)
sftp.close()
c.close()
print("local copy:", local_path, os.path.getsize(local_path), "bytes")
print("BACKUP_DONE")
