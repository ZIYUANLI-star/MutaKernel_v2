"""Recon before E3 campaign ignition: plan builders, existing artifacts."""
import _remote as R

c = R.connect()
R.run(c, "ls /root/mk_v2/scripts/ | grep -iE 'plan|e3|baseline|strategy|fse'",
      timeout=60)
print("### e3_campaign dir")
R.run(c, "ls -la /root/mk_v2_runs/e3_campaign/", timeout=60)
print("### smoke artifacts from earlier plan smoke test")
R.run(c, "ls /root/mk_v2_runs/ | grep -iE 'e3|smoke'", timeout=60)
print("### environment manifest candidates")
R.run(c, "find /root/mk_v2_runs -maxdepth 2 -name '*environment*' "
         "-o -maxdepth 2 -name 'env*.json' 2>/dev/null | head", timeout=60)
c.close()
print("RECON_DONE")
