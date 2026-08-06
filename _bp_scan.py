import re

p = r"MutakernelV2/实验/FSE实验设计_审稿人视角的实验数据蓝图.md"
lines = open(p, encoding="utf-8").read().splitlines()
pat = re.compile(r"\?%|\|\s*\?|\?\s*\||\?\s*(GPU|h\b|个|条)|（\?|\?）|\*\*\?\*\*")
hits = [(i + 1, l.strip()) for i, l in enumerate(lines) if pat.search(l)]
print("total lines with placeholders:", len(hits))
for n, l in hits:
    print(n, l[:120])
