import _remote
c = _remote.connect()
for path, local in [
    ("/root/mk_v2_runs/e1_guard_cse_split.sh", "_dl_guard_cse_split.sh"),
]:
    code, out, err = _remote.run(c, "cat " + path, timeout=60, echo=False)
    with open(local, "w", encoding="utf-8") as f:
        f.write(out)
    print("wrote", local, len(out), "bytes")
print("=== current worker cfg (policies + repeats) ===")
_remote.run(c, "cd /root/mk_v2_runs/e1/e1cse_71e__lrp && ls -la && /root/miniconda3/bin/python -c \"import json;d=json.load(open('cfg_L1_P53__const_perturb__0.json'));print('policies',d.get('stress_policies'));print('repeats',d.get('stress_repeats'),'equiv_runs',d.get('equiv_runs'),'round_timeout',d.get('round_timeout'),'timeout budget via driver')\"", timeout=30)
print("=== current partial result progress ===")
_remote.run(c, "cd /root/mk_v2_runs/e1/e1cse_71e__lrp && /root/miniconda3/bin/python -c \"import json;d=json.load(open('res_L1_P53__const_perturb__0.json'));ts=d.get('trials') or [];from collections import Counter;print('total_trials',len(ts));print('valid_rounds',d.get('valid_rounds'),'round_timeouts',d.get('round_timeouts'),'partial',d.get('partial'));print('by_type',Counter((t.get('round_type'),t.get('status')) for t in ts));print('last policies:',[ (t.get('policy'),t.get('status')) for t in ts[-6:]])\" 2>&1 | tail -20", timeout=30)
c.close()
