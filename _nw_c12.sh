cd /root/mk_v2
echo '=== available aggregators ==='
ls _cse_agg*.py _e1_lanes_agg_remote.py 2>&1
echo '=== how the merge dedups ==='
grep -n 'glob\|bak\|dedup\|outcome' _cse_agg2.py | head -40
