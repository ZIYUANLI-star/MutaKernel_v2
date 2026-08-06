#!/usr/bin/env python3
"""Read-only remote code/context inspection for the CSE slowness analysis."""
import _remote

c = _remote.connect()
CMDS = [
    ("run_worker + timeouts",
     "grep -n 'EQUIV_ROUND_TIMEOUT_S\\|def run_worker\\|BASELINE_PROTOCOL' "
     "/root/mk_v2/scripts/run_e1_probe_study.py | head -20"),
    ("run_worker body",
     "awk '/^def run_worker/,/^def [a-z_]+\\(/' /root/mk_v2/scripts/run_e1_probe_study.py | head -80"),
    ("BASELINE_PROTOCOL body",
     "grep -A12 'BASELINE_PROTOCOL = ' /root/mk_v2/scripts/run_e1_probe_study.py"),
    ("validation timings code",
     "grep -rn 'input_isolation\\|timings\\[\\|synchronize_cuda_timing\\|def _time\\|perf_counter' "
     "/root/mk_v2/src/validation/*.py | head -40"),
    ("validation files", "ls /root/mk_v2/src/validation/"),
    ("driver procs",
     "ps -eo pid,etime,%cpu,%mem,args | grep -E 'run_e1_cse|_mutant_worker' | grep -v grep"),
    ("load + cores", "nproc; cat /proc/loadavg; free -g | sed -n 2p"),
    ("gpus", "nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu --format=csv,noheader"),
    ("kernel shapes P53", "grep -A12 'def get_inputs' $(find /root/mk_v2 -path '*KernelBench*' -name '53_*.py' | grep level1 | head -1)"),
    ("kernel shapes P96", "grep -A12 'def get_inputs' $(find /root/mk_v2 -path '*KernelBench*' -name '96_*.py' | grep level1 | head -1)"),
    ("kernel shapes P16", "grep -A12 'def get_inputs' $(find /root/mk_v2 -path '*KernelBench*' -name '16_*.py' | grep level1 | head -1)"),
    ("kernel shapes P20", "grep -A12 'def get_inputs' $(find /root/mk_v2 -path '*KernelBench*' -name '20_*.py' | grep level1 | head -1)"),
    ("kernel shapes P24", "grep -A12 'def get_inputs' $(find /root/mk_v2 -path '*KernelBench*' -name '24_*.py' | grep level1 | head -1)"),
    ("kernel shapes P27", "grep -A12 'def get_inputs' $(find /root/mk_v2 -path '*KernelBench*' -name '27_*.py' | grep level1 | head -1)"),
    ("kernel shapes P91", "grep -A12 'def get_inputs' $(find /root/mk_v2 -path '*KernelBench*' -name '91_*.py' | grep level1 | head -1)"),
    ("kernel shapes P1 (light)", "grep -A12 'def get_inputs' $(find /root/mk_v2 -path '*KernelBench*' -name '1_*.py' | grep level1 | head -1)"),
    ("policy bank names+size", "grep -n 'def \\|STRESS_POLICIES' /root/mk_v2/src/stress/policy_bank.py | head -40"),
]
for title, cmd in CMDS:
    print("=" * 12, title)
    code, o, e = _remote.run(c, cmd, timeout=120, echo=False)
    print(o.rstrip()[:4000])
    if e.strip():
        print("STDERR:", e.strip()[:500])
c.close()
print("DONE")
