"""Diagnose why the E1 equiv driver process died on the remote A800."""
import _remote

CMDS = [
    ("log_tail", "tail -n 40 /root/mk_v2_runs/e1_equiv.log"),
    ("proc", "ps aux | grep -E 'run_e1|_mutant_worker' | grep -v grep || echo NO_PROCESS"),
    ("uptime", "uptime; cat /proc/uptime; date '+%F %T %z'"),
    ("boot", "who -b 2>/dev/null; uptime -s 2>/dev/null"),
    ("dmesg_oom", "dmesg -T 2>/dev/null | grep -iE 'oom|kill|nvrm|xid' | tail -20 || echo DMESG_UNAVAILABLE"),
    ("dmesg_tail", "dmesg -T 2>/dev/null | tail -15 || true"),
    ("journal", "journalctl -n 30 --no-pager 2>/dev/null | tail -30 || echo JOURNAL_UNAVAILABLE"),
    ("gpu", "nvidia-smi --query-gpu=name,memory.used,utilization.gpu --format=csv 2>&1 | head -3"),
    ("obs_count", "wc -l /root/mk_v2_runs/e1/equiv_observations.jsonl; "
                  "/root/miniconda3/bin/python -c \"import json;print(len(json.load(open('/root/mk_v2_runs/e1/equiv_completed.json'))))\""),
    ("last_obs", "tail -n 1 /root/mk_v2_runs/e1/equiv_observations.jsonl | head -c 600"),
    ("mem", "free -g | head -3; df -h /root | tail -1"),
    ("nohup_out", "ls -la /root/mk_v2_runs/e1_equiv.log; stat -c '%y %s' /root/mk_v2_runs/e1_equiv.log"),
    ("oom_score", "grep -iE 'oom|memory' /var/log/syslog 2>/dev/null | tail -5 || echo NO_SYSLOG"),
]

c = _remote.connect()
for name, cmd in CMDS:
    print(f"===== {name} =====")
    try:
        _remote.run(c, cmd, timeout=60)
    except Exception as exc:
        print("CMD_ERROR:", exc)
c.close()
print("DEATHCHECK_DONE")
