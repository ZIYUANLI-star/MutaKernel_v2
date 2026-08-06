"""Diff the coverage-note edit and assert no filled number was touched."""
import difflib
import re
from pathlib import Path

BASE = Path("MutakernelV2/实验/FSE实验设计_审稿人视角的实验数据蓝图.md.bak_coverage_note")
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
print("numbers in removed lines:", sorted({m for l in removed for m in NUM.findall(l)}))
print("numbers in added lines:", sorted({m for l in added for m in NUM.findall(l)}))
print("\n=== unified diff ===")
for line in difflib.unified_diff(old, new, "before", "after", lineterm="", n=2):
    print(line)
