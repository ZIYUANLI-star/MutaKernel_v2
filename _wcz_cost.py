"""Fetch the round-cost model and check the budget that starved L1_P17."""
import base64
import json
import pathlib

import _wcx

E1 = "/root/mk_v2_runs/e1"
LOCAL = pathlib.Path("_wc_remote")

FLOOR, CAP, STARTUP = 900, 5400, 70.0


def round_cost_s(costs, kernel):
    v = costs.get(kernel)
    if isinstance(v, list):
        v = v[1] or v[0]
        return (v or 500.0) / 1000.0
    return float(v if v is not None else 0.5)


def main():
    with _wcx.Session(label="cost ") as s:
        b64 = s.out("base64 -w0 %s/_wc_round_wall.json" % E1, timeout=120)
        raw = base64.b64decode(b64.strip())
        (LOCAL / "_wc_round_wall.json").write_bytes(raw)
        print("saved _wc_round_wall.json", len(raw), "bytes")
    costs = json.loads(raw.decode("utf-8"))
    print("cost entries:", len(costs))
    print(json.dumps(costs, indent=1)[:1200])

    plan = json.loads((LOCAL / "plan.json").read_text(encoding="utf-8"))
    print("\n=== budget vs. observed for the starved / short cells ===")
    watch = {"L1_P17", "L1_P39", "L1_P37", "L1_P35"}
    for c in plan["control_cells"] + plan["confirm_cells"]:
        if c["kernel"] not in watch:
            continue
        cost = round_cost_s(costs, c["kernel"])
        budget = int(min(CAP, max(FLOOR, 2.5 * c["rounds"] * cost + 2 * STARTUP)))
        print("  %-46s kind=%-7s rounds=%-3d cost/round=%.3fs budget=%ds"
              % (c["cell_id"], c["kind"], c["rounds"], cost, budget))


if __name__ == "__main__":
    main()
