"""Fetch current run5 observations/controls/log for local analysis."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
for remote, local in [
    ("/root/mk_v2_runs/e0_run5_s0/observations.jsonl", "_run5_observations.jsonl"),
    ("/root/mk_v2_runs/e0_run5_s0/original_controls.json", "_run5_controls.json"),
    ("/root/mk_v2_runs/e0_run5_s0.log", "_run5_log.txt"),
    ("/root/mk_v2_runs/e0_run5_s0/run_manifest.json", "_run5_manifest.json"),
]:
    try:
        sftp.get(remote, local)
        print("got", local)
    except Exception as exc:
        print("MISS", remote, type(exc).__name__, str(exc)[:100])
sftp.close()
c.close()
print("FETCH_DONE")
