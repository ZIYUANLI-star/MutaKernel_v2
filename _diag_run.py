import _remote

c = _remote.connect()
_remote.run(c, "tail -15 /root/mk_v2_runs/e1_baseline.log; echo __SEP__; "
               "ls /root/mk_v2_runs/ | grep -i e1; echo __SEP__; "
               "ps aux | grep 'run_e1_probe_[s]tudy' | wc -l; "
               "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader",
            timeout=120)
c.close()
print("PROBE_DONE")
