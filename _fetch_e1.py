"""Fetch current E1 baseline artifacts for local deep validation."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
for remote, local in [
    ("/root/mk_v2_runs/e1/baseline_observations.jsonl", "_e1_observations.jsonl"),
    ("/root/mk_v2_runs/e1/original_controls.json", "_e1_controls.json"),
    ("/root/mk_v2_runs/e1/baseline_run_manifest.json", "_e1_manifest.json"),
    ("/root/mk_v2_runs/e1/probe_manifest.json", "_e1_probe_manifest.json"),
]:
    try:
        sftp.get(remote, local)
        print("got", local)
    except Exception as exc:
        print("MISS", remote, type(exc).__name__, str(exc)[:100])
sftp.close()
c.close()
print("FETCH_DONE")
