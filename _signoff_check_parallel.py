import _remote

c = _remote.connect()
_remote.run(c, (
    "ps aux | grep -E 'signoff|falsify' | grep -v grep; echo ---FILES---; "
    "ls -la /root/mk_v2/_signoff* 2>/dev/null; echo ---LOG---; "
    "tail -8 /root/mk_v2_runs/signoff_go.log 2>/dev/null; echo ---LOGS2---; "
    "ls -la /root/mk_v2_runs/ | grep -i signoff"
), timeout=60)
c.close()
