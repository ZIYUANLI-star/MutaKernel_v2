"""Probe: cores/load, namespace hash function, candidate import mechanics."""
import _remote as R

c = R.connect()
print("### cores + load")
R.run(c, "nproc; uptime; free -g | sed -n 2p", timeout=60)
print("### stable_json_sha256 definition/location")
R.run(c, "grep -rn 'def stable_json_sha256' /root/mk_v2/src/ /root/mk_v2/scripts/run_fse_experiment.py | head -3", timeout=60)
R.run(c, "grep -n 'stable_json_sha256\\|^from\\|^import' /root/mk_v2/scripts/run_fse_experiment.py | head -20", timeout=60)
print("### subjects manifest: candidate path fields")
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json\n"
         "m=json.load(open('/root/mk_v2_runs/e3_campaign/wave1_subject_manifest_v2.json'))\n"
         "s=m['subjects'][0]\n"
         "print('subject_sha256:', s['subject_sha256'][:16])\n"
         "print('candidate:', json.dumps(s['candidate'])[:300])\n"
         "print('n subjects:', len(m['subjects']))\n"
         "EOF", timeout=60)
print("### which cache dirs already exist")
R.run(c, "ls /root/mk_v2_runs/e3_campaign/lane_m_run/torch_extensions/ | wc -l", timeout=60)
c.close()
print("PROBE_DONE")
