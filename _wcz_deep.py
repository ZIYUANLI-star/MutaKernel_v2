"""Pull the audit script, starter log and full lane logs for study (read-only)."""
import pathlib

import _wcx

PY = "/root/miniconda3/bin/python"
WC = "/root/mk_v2_runs/e1/witness_confirmation"
LOCAL = pathlib.Path("_wc_remote")
LOCAL.mkdir(exist_ok=True)

FETCH = [
    ("_wc_audit.py", "cat /root/mk_v2/_wc_audit.py"),
    ("_wc_start.py", "cat /root/mk_v2/_wc_start.py"),
    ("_wc_analyze_remote.py", "cat /root/mk_v2/_wc_analyze.py"),
    ("audit.log", "cat %s/audit.log" % WC),
    ("audit_lane0.log", "cat %s/audit_lane0.log" % WC),
    ("audit_lane1.log", "cat %s/audit_lane1.log" % WC),
    ("starter.log", "cat %s/starter.log" % WC),
    ("control_stdout.log", "cat %s/control_stdout.log" % WC),
]

INLINE = [
    ("plan_summary",
     "%s -c \"import json;p=json.load(open('%s/plan.json'));"
     "print('protocol',json.dumps(p.get('protocol')));"
     "print('control',len(p['control_cells']),'confirm',len(p['confirm_cells']));"
     "print('ctrl_keys',sorted(p['control_cells'][0].keys()));"
     "print('conf_keys',sorted(p['confirm_cells'][0].keys()));"
     "print('conf_example',json.dumps(p['confirm_cells'][0])[:600])\" 2>&1 | tail -20"
     % (PY, WC)),
    ("md5", "md5sum /root/mk_v2/_wc_analyze.py"),
    ("lane_assign",
     "%s -c \"import json;p=json.load(open('%s/plan.json'));"
     "cc=p['confirm_cells'];print('confirm total',len(cc));"
     "import collections;print(collections.Counter(c.get('stage') for c in cc))\" 2>&1 | tail -5"
     % (PY, WC)),
]


def main():
    with _wcx.Session(label="deep ") as s:
        for name, cmd in FETCH:
            txt = s.out(cmd, timeout=180, default="FETCH_FAILED:")
            (LOCAL / name).write_text(txt, encoding="utf-8")
            print("saved %-24s %7d bytes" % (name, len(txt)), flush=True)
        for name, cmd in INLINE:
            print("\n##### %s #####" % name.upper(), flush=True)
            print(s.out(cmd, timeout=120, default="FAILED:").rstrip(), flush=True)
    print("\nDEEP_DONE")


if __name__ == "__main__":
    main()
