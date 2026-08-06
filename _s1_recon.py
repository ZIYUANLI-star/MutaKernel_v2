"""Read the deployed resume/guard/pause scripts and the queue composition."""
import io

import _remote

SCRIPT = r'''
import json
from pathlib import Path

OUT = Path("/root/mk_v2_runs/e3_b9_calib")
for name in ("resume_b9.sh", "guard_b9_v2.sh", "pause_b9.sh"):
    p = OUT / name
    print("################ %s (exists=%s) ################" % (name, p.is_file()))
    if p.is_file():
        print(p.read_text())

st = json.loads((OUT / "queue_state.json").read_text())
units = st["units"]
pending = st["pending"]
print("== queue: pending=%d claimed=%d done=%d units=%d"
      % (len(pending), len(st["claimed"]), len(st["done"]), len(units)))
big = [u for u in pending if units[u]["reserve_gb"] >= 60.0]
small = [u for u in pending if units[u]["reserve_gb"] < 60.0]
print("== reserve >= 60 GiB: %d ; < 60 GiB: %d" % (len(big), len(small)))
req = [u for u in pending if units[u].get("previous_status") in
       ("run_error", "control_timeout", "driver_exception")]
print("== requeued (first wave) %d: %s" % (len(req), req))
print("   of which reserve>=60: %s" % [u for u in req if units[u]["reserve_gb"] >= 60.0])
print("== first-wave unit detail")
hdr = "   %-24s %-10s %9s %9s %10s %10s %8s"
print(hdr % ("unit", "prev", "out_numel", "est_peak", "reserve", "timeout", "fast/slow"))
for u in req:
    d = units[u]
    print("   %-24s %-10s %9.3g %8.1fG %9.1fG %9ds %5d/%d"
          % (u, d.get("previous_status"), d["out_numel"], d["est_peak_gb"],
             d["reserve_gb"], d["unit_timeout_s"], d["est_wall_s_fast"],
             d["est_wall_s_slow"]))
print("== biggest 8 of the >=60GiB tail")
for u in sorted(big, key=lambda x: -units[x]["reserve_gb"])[:8]:
    d = units[u]
    print("   %-24s reserve=%6.1f GiB est_peak=%6.1f GB out_numel=%.3g"
          % (u, d["reserve_gb"], d["est_peak_gb"], d["out_numel"]))
print("== stage-1 (small) serial-hours model")
for key in ("est_wall_s_fast", "est_wall_s_slow"):
    tot_small = sum(units[u][key] for u in small)
    tot_big = sum(units[u][key] for u in big)
    print("   %s: small=%.1f h  big=%.1f h  total=%.1f h (big share %.0f%%)"
          % (key, tot_small / 3600, tot_big / 3600,
             (tot_small + tot_big) / 3600,
             100.0 * tot_big / max(1e-9, tot_small + tot_big)))
Path("/root/_s1_stage_sets.json").write_text(json.dumps(
    {"big": sorted(big), "small": sorted(small), "first_wave": sorted(req)},
    indent=2))
print("wrote /root/_s1_stage_sets.json")
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_s1_recon.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /root/_s1_recon.py", timeout=600)
c.close()
