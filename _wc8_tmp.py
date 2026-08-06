
import json, collections
inv = json.load(open("/root/mk_v2_runs/e1/_wc_witness_inventory.json"))
print("total witnesses:", len(inv))
bykern = collections.defaultdict(list)
for r in inv:
    bykern[r["kernel"]].append(r)

def pos(r):
    d = r.get("divergence") or {}
    return (d.get("round_type"), d.get("policy"), d.get("sub_index"),
            d.get("round_index"), d.get("seed"))

print("\n=== per-kernel witness positions ===")
tot_pos = 0
for k in sorted(bykern, key=lambda x: (-len(bykern[x]), x)):
    rows = bykern[k]
    ps = collections.Counter(pos(r) for r in rows)
    tot_pos += len(ps)
    print(f"\n{k}: {len(rows)} witnesses, {len(ps)} distinct round positions")
    for p, n in sorted(ps.items(), key=lambda kv: str(kv[0])):
        print(f"    x{n}  round_type={p[0]} policy={p[1]} sub_index={p[2]} round_index={p[3]} seed={p[4]}")
    for r in sorted(rows, key=lambda x: x["probe_id"]):
        d = r.get("divergence") or {}
        print(f"      - [{r['stage']}] {r['probe_id']} fc={r['fault_class']} detail={d.get('detail')}")
print("\nTOTAL distinct (kernel, position) audit cells:", tot_pos)

print("\n=== divergence detail kinds ===")
print(collections.Counter((r["stage"], (r.get("divergence") or {}).get("detail")) for r in inv))
print("=== round_type distribution ===")
print(collections.Counter((r["stage"], (r.get("divergence") or {}).get("round_type")) for r in inv))
print("=== fault classes ===")
print(collections.Counter((r["stage"], r["fault_class"]) for r in inv))
