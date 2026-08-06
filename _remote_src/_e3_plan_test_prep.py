
import json, sys
from pathlib import Path
sys.path.insert(0, '/root/mk_v2')
from src.experiments.protocol import plan_from_files

# 3-subject subset manifest (rebuild through the official builder for hashes)
rows = [json.loads(l) for l in
        open('/root/mk_v2_runs/e3_campaign/wave1_manifest_input.jsonl')]
sub = rows[:2] + rows[-1:]   # 2x C3 + 1x C5
with open('/root/mk_v2_runs/e3_campaign/subset_input.jsonl', 'w') as fh:
    for r in sub:
        fh.write(json.dumps(r) + '\n')
print('subset:', [r['subject_id'] for r in sub])
