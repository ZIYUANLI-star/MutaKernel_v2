"""Kill the leftover SERIAL driver (pid 1781) and its worker precisely,
without pattern-matching our own shell. Then check for checkpoint drift."""
import _remote

c = _remote.connect()
print("===== identify serial driver + its workers =====")
_remote.run(c, "ps -eo pid,ppid,args | awk '/run_e1_probe_study/ && !/--lane/ && !/awk/ {print}'", timeout=30)
_remote.run(c, "ps -eo pid,ppid,args | awk '/_mutant_worker/ && !/awk/ {print $1, $2}'", timeout=30)

print("===== kill serial driver 1781 + its workers =====")
_remote.run(
    c,
    "WP=$(ps -eo pid,ppid | awk '$2==1781 {print $1}'); "
    "echo workers_of_1781: $WP; "
    "kill -9 $WP 1781 1780 2>/dev/null; sleep 2; "
    "ps -eo pid,ppid,args | awk '/run_e1_probe_study|_mutant_worker/ && !/awk/ {print $1, $2, $3, $4, $NF}'",
    timeout=60,
)
print("===== global checkpoint after kill (lanes read it at count=72) =====")
_remote.run(c, "wc -l /root/mk_v2_runs/e1/equiv_observations.jsonl; "
               "/root/miniconda3/bin/python -c \"import json; print('global completed:', len(json.load(open('/root/mk_v2_runs/e1/equiv_completed.json'))))\"",
            timeout=30)
print("===== GPU =====")
_remote.run(c, "sleep 3; nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv; "
               "nvidia-smi --query-compute-apps=pid,used_memory --format=csv", timeout=30)
c.close()
print("FIXKILL_DONE")
