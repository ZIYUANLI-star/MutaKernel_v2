"""Is cron available for a keepalive on the chain trigger?"""
import _remote

c = _remote.connect()
for cmd in [
    "which crontab cron crond systemctl 2>&1",
    "ps -eo comm= | sort -u | grep -i -E 'cron|systemd' 2>&1 | head",
    "crontab -l 2>&1 | head -20",
]:
    print("\n#### " + cmd[:70])
    _remote.run(c, cmd, timeout=120)
c.close()
print("\nH19_DONE")
