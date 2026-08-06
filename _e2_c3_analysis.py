# -*- coding: utf-8 -*-
"""Local analysis of the C3 collection frame: figure out the 229 denominator."""
import json
import sys
from collections import Counter, defaultdict

PATH = r"MutakernelV2\实验\补充实验数据\collection_frames\C3_collection_frame.jsonl"

rows = []
with open(PATH, encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if line:
            rows.append(json.loads(line))

print("rows:", len(rows))
tasks_all = set()
tasks_accepted = set()
per_task_accepted = Counter()
levels = Counter()
for r in rows:
    t = r["task_key"]
    tasks_all.add(t)
    levels[t.split("_")[0]] += 0
    if r.get("accepted"):
        tasks_accepted.add(t)
        per_task_accepted[t] += 1

by_level_all = Counter(t.split("_")[0] for t in tasks_all)
by_level_acc = Counter(t.split("_")[0] for t in tasks_accepted)
print("distinct tasks (any row):", len(tasks_all), dict(by_level_all))
print("distinct tasks (>=1 accepted):", len(tasks_accepted), dict(by_level_acc))

# duplicates / accepted counts
acc = sum(1 for r in rows if r.get("accepted"))
dup_w = sum(1 for r in rows if r.get("duplicate_within_corpus"))
print("accepted rows:", acc, "dup_within:", dup_w)

# tasks with rows but zero accepted
none_acc = sorted(tasks_all - tasks_accepted)
print("tasks with no accepted candidate:", len(none_acc))
print(none_acc[:30])
