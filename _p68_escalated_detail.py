"""Pull escalated witness details for L2_P68 and L2_P98."""
import _remote

CMD = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "j = json.load(open('/root/mk_v2_runs/e1/witness_confirmation/wc1_report.json'))\n"
    "for x in (j['verdicts'].values() if isinstance(j['verdicts'], dict) else j['verdicts']):\n"
    "    if isinstance(x, dict) and x.get('probe_id') in ('L2_P68__relop_replace__3', 'L2_P98__mask_boundary__3', 'L1_P49__sync_remove__0'):\n"
    "        print(json.dumps(x, ensure_ascii=False, indent=1))\n"
    "EOF\n"
)

c = _remote.connect()
_, o, _ = _remote.run(c, CMD, timeout=90, echo=False)
c.close()
print(o)
print('P68_DETAIL_DONE')
