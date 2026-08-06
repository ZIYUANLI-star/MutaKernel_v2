#!/usr/bin/env python3
"""Functional test for the ownership-based brake protocol.

Runs entirely inside a scratch directory, so it can be executed on the box while
the real calibration wave is in flight without ever touching the real markers.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/root/mk_v2")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _b9_brake as B

FAILURES = []


def check(label, condition, detail=""):
    print("  [%s] %s%s" % ("ok " if condition else "FAIL", label,
                           ("  -- " + detail) if detail else ""))
    if not condition:
        FAILURES.append(label)


def _ours(root: Path) -> bool:
    return B._derived_is_ours(root)


def run(root: Path):
    derived = B.derived_path(root)

    print("1. empty state")
    current, _ = B.sync(root)
    check("no holders", current == [])
    check("no derived file", not derived.is_file())

    print("2. one owner holds")
    B.hold("witness_audit", "owns the GPU for the P37 witness confirmation",
           "when the audit's control cells are all graded", root)
    current = B.holders(root)
    check("one holder", [o for o, _ in current] == ["witness_audit"])
    check("derived file present", derived.is_file())
    check("derived names the holder", "witness_audit" in derived.read_text())

    print("3. a second owner holds concurrently")
    B.hold("stage1_chain", "critical-path process reappeared", "", root)
    current = B.holders(root)
    check("two holders", [o for o, _ in current] == ["stage1_chain",
                                                     "witness_audit"])
    text = derived.read_text()
    check("derived names both", "stage1_chain" in text and "witness_audit" in text)

    print("4. releasing one holder does NOT release the brake")
    ok, message = B.release("stage1_chain", "automation", root)
    check("release accepted", ok, message)
    check("still one holder", [o for o, _ in B.holders(root)] == ["witness_audit"])
    check("derived still present", derived.is_file(),
          "the last release must be the one that lets lanes run")

    print("5. an owner may not release another owner's marker")
    ok, message = B.release("stage1_chain", "automation", root)
    check("second release of a gone marker refused", not ok, message)
    check("witness_audit untouched",
          [o for o, _ in B.holders(root)] == ["witness_audit"])

    print("6. the last release clears the brake")
    ok, message = B.release("witness_audit", "automation", root)
    check("release accepted", ok, message)
    check("no holders", B.holders(root) == [])
    check("derived file gone", not derived.is_file())
    archived = list((root / "archive").glob("PAUSED_FOR_SIGNOFF_RERUN.released_*"))
    check("derived archived rather than deleted", len(archived) == 1)

    print("7. a foreign brake is tracked, never rewritten or taken over")
    foreign_text = "Paused 2026-07-30 21:45:48 +0800 by pause_b9.sh.\n"
    derived.write_text(foreign_text)
    current, foreign = B.sync(root)
    check("reported as foreign", foreign == B.LEGACY_OWNER, str(foreign))
    check("counted as a holder", [o for o, _ in current] == [B.LEGACY_OWNER])
    check("file content untouched", derived.read_text() == foreign_text,
          "rewriting another party's marker would be a hijack")
    check("observation logged",
          (B.brake_dir(root) / "observed_foreign.jsonl").is_file())

    print("8. a tracked foreign brake is not ours to release")
    for actor in ("automation", "human"):
        ok, message = B.release(B.LEGACY_OWNER, actor, root)
        check("release refused for actor=%s" % actor, not ok, message)
    check("still braked", derived.is_file())

    print("9. our own holders never overwrite a foreign brake")
    B.hold("stage1_chain", "critical path reappeared", "", root)
    current, foreign = B.sync(root)
    check("both holders visible",
          sorted(o for o, _ in current) == ["stage1_chain", B.LEGACY_OWNER],
          str([o for o, _ in current]))
    check("foreign text still intact", derived.read_text() == foreign_text)

    print("10. the placer's own release path works and ours then takes over")
    derived.unlink()                                  # the placer deletes it
    current, foreign = B.sync(root)
    check("foreign holder gone", B.LEGACY_OWNER not in [o for o, _ in current])
    check("our holder still brakes", derived.is_file() and _ours(root))
    ok, message = B.release("stage1_chain", "automation", root)
    check("our release accepted", ok, message)
    check("fully clear", not derived.is_file() and B.holders(root) == [])

    print("11. crash safety: losing our bookkeeping never releases a brake, and")
    print("    does not deadlock either (the in-file sentinel identifies us)")
    B.hold("witness_audit", "second run of the audit", "", root)
    (B.brake_dir(root) / ".derived_state.json").unlink()   # simulate a crash
    current, foreign = B.sync(root)
    check("brake survives the lost state file", derived.is_file())
    check("still recognised as ours, not foreign", foreign is None, str(foreign))
    check("the real owner is the only holder",
          [o for o, _ in current] == ["witness_audit"], str(current))
    ok, message = B.release("witness_audit", "automation", root)
    check("release works after the crash", ok, message)
    current, _ = B.sync(root)
    check("cleared at the end", not derived.is_file() and current == [])

    print("12. a foreign marker can never be mistaken for ours")
    derived.write_text("Paused by pause_b9.sh.\n")
    check("classified foreign without any sidecar",
          B.foreign_brake(root) is not None)
    derived.unlink()


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="b9_brake_test_"))
    print("=== ownership-based brake protocol test ===")
    print("scratch root: %s  (the real run directory is never touched)" % root)
    try:
        run(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("\nBRAKE_TEST_%s (%d failures)"
          % ("FAILED" if FAILURES else "OK", len(FAILURES)))
    for label in FAILURES:
        print("  failed:", label)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
