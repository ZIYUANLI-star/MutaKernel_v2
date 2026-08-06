cd /root/mk_v2
/root/miniconda3/bin/python - <<'PY'
import glob, json, collections
files = sorted(p for p in glob.glob("/root/mk_v2_runs/e1/cse_observations_lane*.jsonl")
               if ".bak" not in p)
print("ledger files:")
recs = {}
dupes = collections.defaultdict(list)
for p in files:
    n = 0
    for line in open(p, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        n += 1
        pid = r["probe_id"]
        dupes[pid].append((p.split('/')[-1], r.get("outcome")))
        recs[pid] = r
    print("  %-62s %4d" % (p.split('/')[-1], n))
print("total unique probes:", len(recs))
c = collections.Counter(r.get("outcome") for r in recs.values())
print("outcomes:", dict(c))
d = {k: v for k, v in dupes.items() if len(v) > 1}
print("probe_ids appearing in >1 record:", len(d))
for k, v in list(d.items())[:15]:
    print("   ", k, v)
print()
print("FALSIFIED probes:")
for pid, r in sorted(recs.items()):
    if r.get("outcome") == "FALSIFIED":
        print("  %-34s %-22s %-24s policy=%-22s round=%-3s seed=%s" % (
            pid, r.get("kernel"), r.get("operator_name"),
            r.get("witness_policy"), r.get("witness_round"), r.get("witness_seed")))
print()
print("INCONCLUSIVE probes:")
for pid, r in sorted(recs.items()):
    if r.get("outcome") == "INCONCLUSIVE":
        print("  %-34s %s" % (pid, r.get("inconclusive_class")))
PY
