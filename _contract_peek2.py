import json
from pathlib import Path

base = Path(r"MutakernelV2\实验\补充实验数据\contracts")
rows = [json.loads(l) for l in
        open(base / "contracts_c2c3c5_draft.jsonl", encoding="utf-8")
        if l.strip()]
print(json.dumps(rows[0], indent=1, ensure_ascii=False)[:4000])
