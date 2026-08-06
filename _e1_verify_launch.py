import _remote

c = _remote.connect()
_, out, _ = _remote.run(c, (
    "ps aux | grep 'run_e1_probe_[s]tudy' | grep -v grep; echo SEP; "
    "tail -c 600 /root/mk_v2_runs/e1_baseline.log; echo SEP; "
    "wc -l < /root/mk_v2_runs/e1/baseline_observations.jsonl; echo SEP; "
    "ls /root/mk_v2_runs/e1/completed.json 2>&1; "
    "/root/miniconda3/bin/python -c \"import json; print('completed entries:', len(json.load(open('/root/mk_v2_runs/e1/completed.json'))))\" 2>&1"
), timeout=90, echo=False)
c.close()
print(out)
print("VERIFY_DONE")
