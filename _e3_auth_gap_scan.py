"""Quantify the contract-authorization gap for the matrix strategies.

For each of the 200 signed contracts, test every case of each strategy in
configs/fse_strategy_matrix.json via assert_case_in_contract. Report per
strategy: contracts fully authorized / partially / which case kinds fail.
"""
import _remote as R

scan_py = r"""
import json, sys
from collections import Counter, defaultdict
sys.path.insert(0, '/root/mk_v2')
from src.experiments.contract import ContractError, assert_case_in_contract

matrix = json.load(open('/root/mk_v2/configs/fse_strategy_matrix.json'))
contracts = {}
for line in open('/root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_signed_v1.jsonl',
                 encoding='utf-8'):
    r = json.loads(line)
    contracts[r['task_key']] = r['contract']

for strat in matrix['strategies']:
    fully, partial = 0, 0
    fail_kinds = Counter()
    fail_tasks = defaultdict(list)
    for tk, ct in contracts.items():
        bad = []
        for case in strat['cases']:
            for seed in case['seeds']:
                probe = {'policy': case['policy'], 'mode': case['mode'],
                         'parameters': case['parameters']}
                try:
                    assert_case_in_contract(probe, ct)
                except ContractError as exc:
                    bad.append((case['policy'], case['mode'],
                                json.dumps(case['parameters'], sort_keys=True),
                                str(exc)[:60]))
                break  # same case for all seeds; one check is enough
        if bad:
            partial += 1
            for b in bad:
                fail_kinds[(b[1], b[2])] += 1
                fail_tasks[(b[1], b[2])].append(tk)
        else:
            fully += 1
    print('== %-28s fully_ok %d / partial %d' % (strat['name'], fully, partial))
    for k, v in sorted(fail_kinds.items(), key=lambda kv: -kv[1]):
        ex = fail_tasks[k][:4]
        print('    blocked case mode=%s params=%s : %d contracts (e.g. %s)'
              % (k[0], k[1], v, ','.join(ex)))
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_e3_auth_scan.py", "w") as fh:
    fh.write(scan_py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _e3_auth_scan.py",
      timeout=600)
c.close()
print("AUTH_SCAN_DONE")
