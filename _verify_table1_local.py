# -*- coding: utf-8 -*-
"""Table 1 本地独立复算:直接读收集帧 jsonl,不信任何汇总报告。"""
import json, collections, hashlib, io, os

BASE = os.path.join('MutakernelV2', '实验', '补充实验数据', 'collection_frames')

def load(p):
    rows = []
    with io.open(p, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

for name in ['C2_collection_frame.jsonl', 'C3_collection_frame.jsonl',
             'C3_subject_frame.jsonl', 'C4_collection_frame.jsonl',
             'C5_collection_frame.jsonl']:
    p = os.path.join(BASE, name)
    rows = load(p)
    inc = sum(1 for r in rows if r.get('included'))
    reasons = collections.Counter(r.get('exclusion_reason') for r in rows if not r.get('included'))
    print('%s: rows=%d included=%d excluded=%s sha256=%s' % (name, len(rows), inc, dict(reasons), sha256(p)))

# C3 任务级:subject frame 每行一个任务代表
c3s = load(os.path.join(BASE, 'C3_subject_frame.jsonl'))
print('C3 subject frame tasks:', len(c3s), 'unique task_key:', len(set(r.get('task_key') for r in c3s)))

# 跨语料重复
x = json.load(io.open(os.path.join(BASE, 'cross_corpus_duplicates.json'), encoding='utf-8'))
print('cross_corpus_duplicates:', json.dumps(x)[:600])

# freeze digest 对照
fz = json.load(io.open(os.path.join(BASE, 'collection_frames.freeze.json'), encoding='utf-8'))
print('freeze keys:', list(fz.keys())[:10])
s = json.dumps(fz)
print('freeze snippet:', s[:800])
