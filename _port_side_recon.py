"""Recon: what port-side executor infrastructure already exists on remote?"""
import _remote as R

c = R.connect()
print("### port executor scripts")
R.run(c, "ls /root/mk_v2/scripts/ | grep -iE 'b7|b8|b9|b11|port|robust|kbenchx|sanitizer|mdir|m_dir'",
      timeout=60)
print("### src port modules")
R.run(c, "find /root/mk_v2/src -iname '*port*' -o -iname '*b7*' -o -iname '*b9*' "
         "-o -iname '*mdir*' 2>/dev/null | head -20", timeout=60)
print("### mdir frozen plans")
R.run(c, "ls /root/mk_v2_runs/e3_campaign/mdir_final/ 2>/dev/null | head -5; "
         "ls /root/mk_v2_runs/e3_campaign/mdir_final/ 2>/dev/null | wc -l", timeout=60)
print("### b9 calibrated tolerances availability")
R.run(c, "ls /root/mk_v2_runs/e3_b9_calib/ | head -8", timeout=60)
c.close()
print("RECON_DONE")
