import _remote

CMD = (
    "sed -n '40,140p' /root/mk_v2/_signoff_go.py; echo ---STEPDE---; "
    "grep -n 'pgrep\\|already\\|running\\|def step' /root/mk_v2/_signoff_go.py; echo ---SUMMARY---; "
    "cat /root/mk_v2_runs/e1/signoff_summary.json 2>/dev/null; echo ---AUDIT---; "
    "cat /root/mk_v2/_signoff_audit_remote.py 2>/dev/null | head -50; echo ---PSNOW---; "
    "ps aux | grep -E 'signoff|falsify' | grep -v grep"
)
c = _remote.connect()
_remote.run(c, CMD, timeout=120)
c.close()
