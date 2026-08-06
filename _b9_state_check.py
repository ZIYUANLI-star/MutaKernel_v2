import _remote

c = _remote.connect()
_remote.run(c, (
    "ls /root/mk_v2_runs/e3_b9_calib/ | head -20; echo ---UNITS---; "
    "ls /root/mk_v2_runs/e3_b9_calib/units/ 2>/dev/null | wc -l; "
    "ls /root/mk_v2_runs/e3_b9_calib/units/ 2>/dev/null | head -10; echo ---ORCH---; "
    "ps aux | grep -E 'b9|e3' | grep -v grep | head -10; echo ---LOGS---; "
    "ls -la --time-style=+%H:%M /root/mk_v2_runs/ | grep -iE 'b9|e3' | head; echo ---TAIL---; "
    "for f in /root/mk_v2_runs/e3_b9*.log /root/mk_v2_runs/e3_b9_calib/*.log; do "
    "[ -f \"$f\" ] && echo \"## $f\" && tail -5 \"$f\"; done 2>/dev/null; "
    "echo ---GPU---; nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; "
    "echo ---DONE_MARKERS---; ls /root/mk_v2_runs/e3_b9_calib/units/*/result.json 2>/dev/null | wc -l"
), timeout=120)
c.close()
