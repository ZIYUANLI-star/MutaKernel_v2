import json
import _remote

REMOTE_SNIPPET = (
    "grep -h P53__arith_replace__17 /root/mk_v2_runs/e1/cse_observations_lane3.jsonl "
    "| head -1; echo ---LOGTAIL---; "
    "ls /root/mk_v2_runs/*.log 2>/dev/null | tail -10; "
    "grep -ln P53__arith_replace__17 /root/mk_v2_runs/*.log 2>/dev/null"
)

c = _remote.connect()
_, out, _ = _remote.run(c, REMOTE_SNIPPET, timeout=120, echo=False)
c.close()

raw, _, logtail = out.partition("---LOGTAIL---")
raw = raw.strip()
if raw:
    r = json.loads(raw)
    trials = r.pop("trials", [])
    for k, v in r.items():
        s = json.dumps(v, ensure_ascii=False)
        if len(s) > 600:
            s = s[:600] + "...(truncated)"
        print(f"{k} = {s}")
    print(f"--- last 5 of {len(trials)} trials ---")
    for t in trials[-5:]:
        print(json.dumps(t, ensure_ascii=False)[:400])
print("---LOGTAIL---")
print(logtail.strip()[:2000])
print("P53_DIAG_DONE")
