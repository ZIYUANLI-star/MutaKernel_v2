#!/usr/bin/env python3
"""Deploy the gated code following the 5.1.1 precedent flow.

backup -> install -> py_compile in place -> ledger baseline -> kill DRIVERS
FIRST then workers (order matters: killing a worker first would let the
driver grade a spurious INCONCLUSIVE into the ledger) -> guard AUTORESTART.
"""
import time

import _remote

c = _remote.connect()


def run(cmd, timeout=120, title=None):
    if title:
        print("=" * 12, title)
    code, o, e = _remote.run(c, cmd, timeout=timeout, echo=False)
    print(o.rstrip()[-2200:])
    if e.strip():
        print("STDERR:", e.strip()[-500:])
    return code, o


# 0) ledger baseline
run("wc -l /root/mk_v2_runs/e1/cse_observations_lane3.jsonl "
    "/root/mk_v2_runs/e1/cse_observations_lane4.jsonl; "
    "md5sum /root/mk_v2_runs/e1/cse_completed_lane3.json "
    "/root/mk_v2_runs/e1/cse_completed_lane4.json", title="ledger baseline")

# 1) backup originals (timestamped, non-.py suffix so pytest ignores them)
run("cp -a /root/mk_v2/scripts/_mutant_worker.py "
    "/root/mk_v2/scripts/_mutant_worker.py.bak_20260728_preopt && "
    "cp -a /root/mk_v2/scripts/run_e1_cse_falsify.py "
    "/root/mk_v2/scripts/run_e1_cse_falsify.py.bak_20260728_preopt && "
    "ls -la /root/mk_v2/scripts/*.bak_20260728_preopt", title="backup")

# 2) install gated staged files + new test
run("cp /tmp/_mk_stage/_mutant_worker.py /root/mk_v2/scripts/_mutant_worker.py && "
    "cp /tmp/_mk_stage/run_e1_cse_falsify.py /root/mk_v2/scripts/run_e1_cse_falsify.py && "
    "cp /tmp/_mk_stage/test_gen_opt_bitexact.py /root/mk_v2/tests/test_gen_opt_bitexact.py && "
    "md5sum /root/mk_v2/scripts/_mutant_worker.py /root/mk_v2/scripts/run_e1_cse_falsify.py "
    "/tmp/_mk_stage/_mutant_worker.py /tmp/_mk_stage/run_e1_cse_falsify.py", title="install")

# 3) py_compile in place
code, _ = run("/root/miniconda3/bin/python -m py_compile "
              "/root/mk_v2/scripts/_mutant_worker.py "
              "/root/mk_v2/scripts/run_e1_cse_falsify.py && echo INPLACE_COMPILE_OK",
              title="py_compile in place")
if code != 0:
    print("ABORT: in-place compile failed; restoring backups")
    run("cp -a /root/mk_v2/scripts/_mutant_worker.py.bak_20260728_preopt "
        "/root/mk_v2/scripts/_mutant_worker.py && "
        "cp -a /root/mk_v2/scripts/run_e1_cse_falsify.py.bak_20260728_preopt "
        "/root/mk_v2/scripts/run_e1_cse_falsify.py")
    raise SystemExit(1)

# 4) snapshot current processes, then kill drivers FIRST, workers second
run("ps -eo pid,ppid,args | grep -E 'run_e1_cse_falsify|_mutant_worker' "
    "| grep -v grep", title="processes before kill")
run("DRV=$(pgrep -f 'run_e1_cse_falsify.py.*--lane [34]' | tr '\\n' ' '); "
    "echo DRIVERS: $DRV; kill -9 $DRV 2>/dev/null; sleep 1; "
    "WRK=$(pgrep -f '_mutant_worker.py' | tr '\\n' ' '); echo WORKERS: $WRK; "
    "for p in $WRK; do kill -9 -$p 2>/dev/null || kill -9 $p 2>/dev/null; done; "
    "sleep 1; ps -eo pid,args | grep -E 'run_e1_cse_falsify|_mutant_worker' "
    "| grep -v grep; echo KILL_DONE", title="kill drivers then workers")

# 5) ledger must be unchanged by the kill
run("wc -l /root/mk_v2_runs/e1/cse_observations_lane3.jsonl "
    "/root/mk_v2_runs/e1/cse_observations_lane4.jsonl; "
    "md5sum /root/mk_v2_runs/e1/cse_completed_lane3.json "
    "/root/mk_v2_runs/e1/cse_completed_lane4.json", title="ledger after kill")

# 6) wait for guard AUTORESTART (cycle is 120s)
print("=" * 12, "waiting for guard AUTORESTART (up to 300s)")
for i in range(10):
    time.sleep(30)
    code, o = run("pgrep -af 'run_e1_cse_falsify.py.*--lane [34]' | cat")
    if o.strip().count("run_e1_cse_falsify") >= 2:
        print(f"both lanes back after ~{(i + 1) * 30}s")
        break

# 7) health: log tails, manifest marker, new workers
run("tail -3 /root/mk_v2_runs/e1_cse_lane3.log; echo ----; "
    "tail -3 /root/mk_v2_runs/e1_cse_lane4.log", title="driver logs")
run("grep -o '\"input_pipeline\": \"[^\"]*\"' "
    "/root/mk_v2_runs/e1/cse_run_manifest_lane3.json "
    "/root/mk_v2_runs/e1/cse_run_manifest_lane4.json", title="manifest marker")
run("ps -eo pid,etime,args | grep -E 'run_e1_cse_falsify|_mutant_worker' "
    "| grep -v grep", title="processes after restart")
c.close()
print("DEPLOY_SEQUENCE_DONE")
