"""Final steady-state check after guard v10.1 rollout."""
import _remote

c = _remote.connect()
_remote.run(c, "cat /root/mk_v2_runs/e1_guard.pid; "
               "ps -eo pid,args | grep -E 'e1_guard_cse_[s]plit' ; "
               "ps -eo pid,args | grep 'run_e1_cse_[f]alsify.py --out' "
               "| grep -v bash; "
               "free -g | sed -n 2p; "
               "nvidia-smi --query-gpu=memory.used --format=csv,noheader; "
               "for L in 3 4 5; do "
               "wc -l /root/mk_v2_runs/e1/cse_observations_lane$L.jsonl; done",
            timeout=60)
c.close()
print("FINAL_CHECK_DONE")
