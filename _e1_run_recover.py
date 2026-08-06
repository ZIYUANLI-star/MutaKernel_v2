import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_e1_recover_remote.py", "/root/mk_v2/_e1_recover_remote.py")
sftp.close()
print("===== env check =====")
_remote.run(c, "date '+%F %T %z'; uptime; nvidia-smi --query-gpu=name,memory.used --format=csv; "
               "ls /root/mk_v2_runs/torch_ext 2>/dev/null | wc -l; "
               "/root/miniconda3/bin/python -c \"import torch; print('torch', torch.__version__, 'cuda_ok', torch.cuda.is_available())\"; "
               "ps -eo args | grep -E 'run_e1|e1_guard' | grep -v grep || echo NO_E1_PROCESSES",
            timeout=120)
print("===== integrity + aggregation =====")
_remote.run(c, "/root/miniconda3/bin/python /root/mk_v2/_e1_recover_remote.py", timeout=300)
c.close()
print("RUN_RECOVER_DONE")
