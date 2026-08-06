"""Repair the L1_P17 control cell that was starved by a stale build lock.

The extension build directory matmul_cuda_eqm_L1_P17__WC_AUDIT_CONTROL__equiv
is the only one of the 38 WC_AUDIT_CONTROL builds with no .so and a leftover
`lock` file: a worker was killed mid-compile at 20:57:51, so every later attempt
blocked on torch's build baton until the 900s worker budget expired (zero rounds
recorded, twice).  Both artefacts are moved aside rather than deleted, then the
single control cell is re-queued on the now-idle lane 0.
"""
import _wcx

PY = "/root/miniconda3/bin/python"
MK = "/root/mk_v2"
WC = "/root/mk_v2_runs/e1/witness_confirmation"
EXT = "/root/mk_v2_runs/torch_ext"
BAD = EXT + "/matmul_cuda_eqm_L1_P17__WC_AUDIT_CONTROL__equiv"
CELL = WC + "/cells/ctrl__L1_P17__equiv__head_heavy"

PRE = (
    "set -e; "
    "test -f %s/lock && echo LOCK_PRESENT || echo LOCK_ABSENT; "
    "ls %s/*.so 2>/dev/null | wc -l; "
    "echo '--- lane0 lock holder ---'; cat %s/audit_lane0.lock 2>/dev/null; "
    "echo '--- lane0 audit alive? ---'; "
    "ps -eo pid,cmd | grep '_wc_audit.py' | grep 'lane 0' | grep -v grep | wc -l; "
    "echo '--- STAGE_DONE ---'; ls %s/STAGE_DONE* 2>/dev/null"
    % (BAD, BAD, WC, WC)
)

MOVE = (
    "set -e; ts=$(date +%%Y%%m%%dT%%H%%M%%S); "
    "mv %s %s.stale_lock_$ts && echo MOVED_BUILD_DIR; "
    "mv %s.json %s.json.starved_stale_lock_$ts && echo MOVED_CELL_JSON; "
    "ls -d %s* 2>/dev/null; ls %s.json* 2>/dev/null"
    % (BAD, BAD, CELL, CELL, BAD, CELL)
)

LAUNCH = (
    "cd %s && setsid %s -u _wc_audit.py run --stage control --only L1_P17 "
    "--n-a 10 --n-b 20 --lane 0 --lanes 1 "
    "> %s/p17_fix_stdout.log 2>&1 < /dev/null & echo LAUNCHED; sleep 3; "
    "ps -eo pid,cmd | grep _wc_audit | grep -v grep"
    % (MK, PY, WC)
)


def main():
    with _wcx.Session(label="p17fix ") as s:
        print("##### PRECHECK #####")
        print(s.out(PRE, timeout=120).rstrip())
        print("\n##### MOVE ASIDE #####")
        print(s.out(MOVE, timeout=120).rstrip())
        print("\n##### LAUNCH #####")
        print(s.out(LAUNCH, timeout=120).rstrip())
    print("\nP17FIX_DONE")


if __name__ == "__main__":
    main()
