"""Build + freeze the deployment-grade FaultToStressMap from closed E1 data.

Blueprint 5.1.1 freeze discipline: the map must be built on all of C1 and
content-hashed BEFORE any C2-C5 subject is executed.  This runs the
preregistered `run_e1_probe_study.py --phase map` on the amended E1 ledgers
(equiv_observations.jsonl + baseline_observations.jsonl), then:
  * sha256-freezes fault_to_stress_map.json,
  * archives a frozen copy + freeze manifest under e3_campaign/,
  * prints escape_mechanisms.json (the 5.5 escape-mechanism sentence source)
    and the pooled crossfit numbers for cross-checking against a1.
CPU-only; does not touch the running B9 stage-2 lanes.
"""
import json

import _remote

c = _remote.connect()

# guard: phase map must exist in the remote script version
code, o, e = _remote.run(
    c, "grep -c 'def phase_map' /root/mk_v2/scripts/run_e1_probe_study.py",
    timeout=60, echo=False)
if o.strip() != "1":
    raise SystemExit("remote run_e1_probe_study.py lacks phase_map: %r" % o)

# ledger presence + row counts (sanity)
_remote.run(c, "wc -l /root/mk_v2_runs/e1/equiv_observations.jsonl "
               "/root/mk_v2_runs/e1/baseline_observations.jsonl", timeout=60)

# build the map (CPU, reads ledgers, writes 3 JSONs into e1/)
code, o, e = _remote.run(
    c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u "
       "scripts/run_e1_probe_study.py --phase map "
       "--out-dir /root/mk_v2_runs/e1",
    timeout=900)
if code != 0:
    raise SystemExit("phase map failed")

# freeze: digest + archived copy + manifest
freeze_cmd = r"""
cd /root/mk_v2_runs/e1 || exit 1
mkdir -p /root/mk_v2_runs/e3_campaign
MAP=fault_to_stress_map.json
DIG=$(sha256sum $MAP | cut -d' ' -f1)
EQD=$(sha256sum equiv_observations.jsonl | cut -d' ' -f1)
BLD=$(sha256sum baseline_observations.jsonl | cut -d' ' -f1)
cp $MAP /root/mk_v2_runs/e3_campaign/fault_to_stress_map_frozen.json
/root/miniconda3/bin/python - "$DIG" "$EQD" "$BLD" <<'PY'
import json, sys, datetime
dig, eqd, bld = sys.argv[1:4]
m = {
  "frozen_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "map_file": "/root/mk_v2_runs/e3_campaign/fault_to_stress_map_frozen.json",
  "map_sha256": dig,
  "basis": {
    "equiv_observations_sha256": eqd,
    "baseline_observations_sha256": bld,
    "ledger_state": "post wc1_closure_v1 amendment (2026-08-01)",
  },
  "discipline": "blueprint 5.1.1: frozen before any C2-C5 subject execution;"
                " zero C2-C5 subjects executed at freeze time",
  "builder": "scripts/run_e1_probe_study.py --phase map (e1-map-v1)",
}
open("/root/mk_v2_runs/e3_campaign/map_freeze_manifest.json","w").write(
    json.dumps(m, indent=2))
print("FREEZE_MANIFEST_WRITTEN sha256=" + dig)
PY
"""
code, o, e = _remote.run(c, freeze_cmd, timeout=120)

# report the two analysis artifacts
_remote.run(c, "cat /root/mk_v2_runs/e1/escape_mechanisms.json", timeout=60)
_remote.run(c, "/root/miniconda3/bin/python -c \"import json;"
               "d=json.load(open('/root/mk_v2_runs/e1/map_crossfit_evaluation.json'));"
               "print(json.dumps({'pooled': d.get('pooled'),"
               " 'folds': len(d.get('folds', []))}, indent=1))\"", timeout=60)
_remote.run(c, "/root/miniconda3/bin/python -c \"import json;"
               "d=json.load(open('/root/mk_v2_runs/e1/fault_to_stress_map.json'));"
               "print('map_version', d.get('map_version'));"
               "print('witnessed_probe_count', d.get('witnessed_probe_count'));"
               "print('fault_classes', len(d.get('entries', d.get('map', {}))))\"",
            timeout=60)
c.close()
print("MAP_FREEZE_DONE")
