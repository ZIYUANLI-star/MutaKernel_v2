"""Fetch the plan, witness inventory and round counts for offline analysis."""
import base64
import pathlib

import _wcx

E1 = "/root/mk_v2_runs/e1"
WC = E1 + "/witness_confirmation"
LOCAL = pathlib.Path("_wc_remote")
LOCAL.mkdir(exist_ok=True)

FILES = {
    "plan.json": WC + "/plan.json",
    "_wc_witness_inventory.json": E1 + "/_wc_witness_inventory.json",
    "_wc_round_counts.json": E1 + "/_wc_round_counts.json",
    "_wc_seed_shortcut.json": E1 + "/_wc_seed_shortcut.json",
    "wc1_report.json": WC + "/wc1_report.json",
}


def main():
    with _wcx.Session(label="fetch ") as s:
        for name, path in FILES.items():
            # base64 keeps the transfer binary-safe and lets us verify length
            out = s.out("base64 -w0 %s 2>/dev/null" % path, timeout=300,
                        default="FAILED:")
            if out.startswith("FAILED:") or not out.strip():
                print("!! %-32s could not be fetched (%s)" % (name, out[:80]))
                continue
            raw = base64.b64decode(out.strip())
            (LOCAL / name).write_bytes(raw)
            print("saved %-32s %8d bytes" % (name, len(raw)))
    print("FETCH_DONE")


if __name__ == "__main__":
    main()
