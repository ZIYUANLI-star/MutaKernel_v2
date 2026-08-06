"""Full read-only status probe of the WC-1 witness-confirmation audit."""
import _wcx

WC = "/root/mk_v2_runs/e1/witness_confirmation"

CMDS = [
    ("stage_done",
     "date '+%%F %%T'; echo ---; ls -la %s/STAGE_DONE* 2>/dev/null || echo NO_STAGE_DONE; "
     "echo ---; ls -la %s/ | head -40" % (WC, WC)),
    ("lane0", "tail -n 25 %s/audit_lane0.log 2>/dev/null; echo '---MTIME'; "
              "stat -c '%%y %%n' %s/audit_lane0.log 2>/dev/null" % (WC, WC)),
    ("lane1", "tail -n 25 %s/audit_lane1.log 2>/dev/null; echo '---MTIME'; "
              "stat -c '%%y %%n' %s/audit_lane1.log 2>/dev/null" % (WC, WC)),
    ("cells", "ls %s/cells/*.json 2>/dev/null | wc -l; echo '---NEWEST'; "
              "ls -lt %s/cells/*.json 2>/dev/null | head -6" % (WC, WC)),
    ("report", "python3 -c \"import json;d=json.load(open('%s/wc1_report.json'));"
               "print('cells_done',d.get('cells_done'),'planned',d.get('cells_planned'));"
               "print('states',d.get('control_cell_states'));"
               "print('generated',d.get('generated_at'))\" 2>&1 | tail -5" % WC),
    ("procs", "ps -eo pid,ppid,etimes,rss,stat,cmd | grep -E '_wc_audit|_wc_start|"
              "mutant_worker|witness_conf' | grep -v grep"),
    ("gpu", "nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu "
            "--format=csv,noheader; echo ---; "
            "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader"),
    ("oom", "for p in /sys/fs/cgroup/memory.events /sys/fs/cgroup/memory.events.local "
            "/sys/fs/cgroup/memory/memory.oom_control /sys/fs/cgroup/memory/memory.failcnt; do "
            "if [ -e $p ]; then echo \"== $p\"; cat $p; fi; done; echo '---DMESG'; "
            "(dmesg 2>/dev/null | grep -ci 'killed process' || echo dmesg_unavailable)"),
    ("brake", "ls -la /root/mk_v2_runs/b9*/ 2>/dev/null | head -30; echo '---BRAKEFILES'; "
              "find /root/mk_v2_runs -maxdepth 3 -iname '*brake*' -printf '%T@ %p\\n' "
              "2>/dev/null | sort -n | tail -20"),
    ("startlog", "ls -t /root/mk_v2_runs/e1/*wc_start* /root/mk_v2_runs/e1/**/*wc_start* "
                 "2>/dev/null | head; echo ---; "
                 "for f in $(ls -t /root/mk_v2_runs/e1/_wc_start*.log %s/_wc_start*.log "
                 "2>/dev/null | head -2); do echo \"== $f\"; tail -n 30 $f; done" % WC),
    ("plan", "python3 -c \"import json;p=json.load(open('%s/plan.json'));"
             "print('protocol',p.get('protocol'));"
             "print('control_cells',len(p['control_cells']),'confirm_cells',len(p['confirm_cells']))\" "
             "2>&1 | tail -5" % WC),
    ("scripts", "ls -la /root/mk_v2/_wc*.py /root/mk_v2_runs/e1/_wc*.json 2>/dev/null"),
]


def main():
    with _wcx.Session(label="probe ") as s:
        for name, cmd in CMDS:
            print("\n##### %s #####" % name.upper(), flush=True)
            print(s.out(cmd, timeout=120, default="PROBE_FAILED:").rstrip(), flush=True)
    print("\nPROBE_DONE")


if __name__ == "__main__":
    main()
