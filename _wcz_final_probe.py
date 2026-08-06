"""Post-completion probe: final lane logs, B9 resumption, brake archive."""
import _wcx

WC = "/root/mk_v2_runs/e1/witness_confirmation"
B9 = "/root/mk_v2_runs/e3_b9_calib"

CMDS = [
    ("lane0_full_tail", "tail -n 60 %s/audit_lane0.log" % WC),
    ("lane1_tail", "tail -n 25 %s/audit_lane1.log" % WC),
    ("stage_done_files", "ls -la --time-style=+%%F_%%T %s/STAGE_DONE* %s/STARTER_DONE "
                         "2>/dev/null" % (WC, WC)),
    ("starter_log", "tail -n 12 %s/starter.log" % WC),
    ("who_ran_lane0_again",
     "grep -n 'audit start' %s/audit_lane0.log; echo ---; "
     "tail -n 5 %s/p17_fix_stdout.log 2>/dev/null; "
     "tail -c 800 %s/lane0_stdout.log" % (WC, WC, WC)),
    ("cells_count", "ls %s/cells/*.json | wc -l; "
                    "ls -la --time-style=+%%F_%%T %s/cells/ctrl__L1_P17__equiv__head_heavy.json "
                    "%s/cells/conf__L1_P17__launch_config_mutate__0__equiv.json 2>/dev/null"
     % (WC, WC, WC)),
    ("b9_state",
     "ls -la --time-style=+%%F_%%T %s/ | head -25; echo '---ARCHIVE'; "
     "ls -la --time-style=+%%F_%%T %s/archive/ 2>/dev/null | tail -5; echo '---PROCS'; "
     "ps -eo pid,etimes,cmd | grep -E 'b9|guard' | grep -v grep; echo '---GPU'; "
     "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; "
     "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader"
     % (B9, B9)),
    ("b9_progress",
     "for f in $(ls -t %s/*.log 2>/dev/null | head -3); do echo \"== $f\"; "
     "tail -n 6 $f; done" % B9),
    ("oom_final", "grep '^oom_kill ' /sys/fs/cgroup/memory/memory.oom_control"),
]


def main():
    with _wcx.Session(label="final ") as s:
        for name, cmd in CMDS:
            print("\n##### %s #####" % name.upper(), flush=True)
            print(s.out(cmd, timeout=150, default="PROBE_FAILED:").rstrip(), flush=True)
    print("\nFINAL_PROBE_DONE")


if __name__ == "__main__":
    main()
