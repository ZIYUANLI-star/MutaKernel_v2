"""Identify what re-ran the L1_P17 control cell at 00:41 (read-only)."""
import _wcx

EXT = "/root/mk_v2_runs/torch_ext"

CMDS = [
    ("cron", "crontab -l 2>&1 | head -30; echo ---; ls /etc/cron.d/ 2>/dev/null; "
             "atq 2>&1 | head"),
    ("ext_now", "ls -la --time-style=+%%F_%%T %s/ 2>/dev/null | grep -i 'P17__WC' ; "
                "ls %s/matmul_cuda_eqm_L1_P17__WC_AUDIT_CONTROL__equiv/ 2>/dev/null"
     % (EXT, EXT)),
    ("recent_scripts",
     "ls -lt --time-style=+%F_%T /root/mk_v2/_wc*.py /root/mk_v2/*.sh 2>/dev/null | head -12; "
     "echo ---; for f in /root/mk_v2/_wc40_tmp.py /root/mk_v2/_wc39_tmp.py; do "
     "echo \"== $f\"; head -c 1200 $f; done"),
    ("proc_311628", "ls /proc/311628 2>/dev/null && cat /proc/311628/cmdline "
                    "| tr '\\0' ' ' || echo PROC_GONE"),
    ("bash_history", "tail -n 25 /root/.bash_history 2>/dev/null"),
    ("keepalive", "cat /root/mk_v2_runs/e3_b9_calib/keepalive_stage1.sh 2>/dev/null | head -40"),
    ("wc_repair_hits", "grep -rln 'only L1_P17\\|only.*P17' /root/mk_v2/*.py "
                       "/root/mk_v2_runs/e1/*.sh 2>/dev/null | head"),
]


def main():
    with _wcx.Session(label="who ") as s:
        for name, cmd in CMDS:
            print("\n##### %s #####" % name.upper(), flush=True)
            print(s.out(cmd, timeout=150, default="PROBE_FAILED:").rstrip(), flush=True)
    print("\nWHO_DONE")


if __name__ == "__main__":
    main()
