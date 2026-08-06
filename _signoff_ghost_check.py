import _remote

CMD = (
    "stat -c '%n %y %s' /root/mk_v2/_signoff_go.py /root/mk_v2/_signoff_audit_remote.py "
    "/root/mk_v2/_signoff_go_remote.py 2>/dev/null; echo ---HEAD---; "
    "head -40 /root/mk_v2/_signoff_go.py; echo ---PS---; "
    "ps aux | grep -E 'run_e1_cse_falsify|signoff' | grep -v grep; echo ---SSH---; "
    "who; ls /root/mk_v2 -la --time-style=+%H:%M:%S | tail -20; echo ---LOG---; "
    "tail -8 /root/mk_v2_runs/e1_cse_lane3_signoff_requeue.log; echo ---TAGGED---; "
    "ls -la --time-style=+%H:%M:%S /root/mk_v2_runs/e1/*signoff* 2>/dev/null"
)
c = _remote.connect()
_remote.run(c, CMD, timeout=120)
c.close()
