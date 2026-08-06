"""Show the blueprint diff and assert no already-filled number was touched."""
import difflib
import re
from pathlib import Path

BASE = Path("MutakernelV2/实验/FSE实验设计_审稿人视角的实验数据蓝图.md.bak_oracle_clause")
NEW = Path("MutakernelV2/实验/FSE实验设计_审稿人视角的实验数据蓝图.md")

old = BASE.read_text(encoding="utf-8").splitlines()
new = NEW.read_text(encoding="utf-8").splitlines()

print("lines: %d -> %d" % (len(old), len(new)))
print("'?' occurrences: %d -> %d"
      % (sum(l.count("?") for l in old), sum(l.count("?") for l in new)))

removed = [l for l in difflib.unified_diff(old, new, lineterm="", n=0)
           if l.startswith("-") and not l.startswith("---")]
added = [l for l in difflib.unified_diff(old, new, lineterm="", n=0)
         if l.startswith("+") and not l.startswith("+++")]
print("removed lines: %d ; added lines: %d" % (len(removed), len(added)))

NUM = re.compile(r"\d+(?:\.\d+)?\s*%|\b\d{2,}\b|\d+\.\d+e[+-]?\d+|\d+/\d+")


def numbers(lines):
    bag = []
    for line in lines:
        bag += NUM.findall(line)
    return bag


print("\n=== numbers present in removed lines ===")
print(sorted(set(numbers(removed))))
print("\n=== numbers present in added lines ===")
print(sorted(set(numbers(added))))

print("\n=== unified diff ===")
for line in difflib.unified_diff(old, new, "before", "after", lineterm="", n=2):
    print(line)
