#!/usr/bin/env python3
"""Ownership-based brake protocol for the B9 calibration run.

Deployed to /root/mk_v2/_b9_brake.py.  Usable as a library and as a CLI:

    python _b9_brake.py status
    python _b9_brake.py hold  <owner> --reason "..." [--release-when "..."]
    python _b9_brake.py release <owner> [--actor human]
    python _b9_brake.py sync

Why this replaces the single unsigned marker
--------------------------------------------
The deployed run used one file, PAUSED_FOR_SIGNOFF_RERUN, with no record of who
placed it.  Any component that wanted the GPU back therefore had to guess
whether a brake was still needed, and the deployed chain trigger guessed by
polling for critical-path processes: two consecutive clean polls and it lifted
the brake.  That is *probabilistic* -- a party whose workers have a gap longer
than two polls has its brake silently removed, and because a lane honours the
brake only *between* units, the lane can then start a unit that runs for up to
four hours alongside the other party.  Exactly that overlap OOM-killed a
critical-path worker earlier in this campaign.

Narrowing the polling window reduces the probability; it does not remove the
failure class, because the other party's gaps can be arbitrarily long.  The fix
is to make the brake carry its owner:

  1. every party that needs B9 suppressed writes its own signed marker
     brakes/BRAKE_BY_<owner>, recording who, when, why and the expected release
     condition;
  2. a marker is released only by its owner, or by a human explicitly.  No
     automation removes another party's marker -- there is nothing to guess;
  3. lanes may start only when *no* marker exists.  Several parties can hold the
     brake at once and the last release lets the run continue, which makes the
     multi-party case race-free rather than last-writer-wins;
  4. the historical PAUSED_FOR_SIGNOFF_RERUN is not ignored, and it is also not
     taken over.  A copy of that file which we did not write counts as a holder
     named ``unknown_legacy`` *for exactly as long as the file exists*, and it is
     released the way its placer expects -- by that placer deleting the file.
     We record the observation and otherwise leave the file alone.

The deployed guard and lane driver still read PAUSED_FOR_SIGNOFF_RERUN, so this
module keeps that file as a *derived* view of the holder set: present with the
holders listed whenever at least one of our markers exists, absent when none do.
That leaves the audited guard/lane code untouched.

Tracking a foreign brake instead of adopting it is the difference between a
protocol and a hijack.  An earlier version of this module converted the foreign
file into a marker of its own and declared it human-release-only.  That is wrong
in both directions: it rewrote another party's file, and it turned a brake its
placer would have released on its own into one that needed a human, which would
have stalled the run the moment the placer released it.  So: never write the
derived file while a foreign one is present, and never claim to own it.

Failure mode is deliberately asymmetric: the derived file is only ever removed
after positively observing an empty holder set.  There is no cleanup-on-exit
path, so a crash of whatever process runs sync() leaves every brake in force.
Crashing means "stays braked", never "brake released".
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

OUT = Path("/root/mk_v2_runs/e3_b9_calib")
BRAKE_DIR_NAME = "brakes"
PREFIX = "BRAKE_BY_"
LEGACY_NAME = "PAUSED_FOR_SIGNOFF_RERUN"
LEGACY_OWNER = "unknown_legacy"
# first line of a derived file; lets us recognise our own writing even if the
# sidecar is lost, and can never appear in a foreign pause_b9.sh marker
SENTINEL = "#b9-brake-derived-v1"
# owners whose marker no automation may release; only an explicit human release
HUMAN_RELEASE_ONLY = (LEGACY_OWNER, "human")


def brake_dir(root: Path = OUT) -> Path:
    return root / BRAKE_DIR_NAME


def derived_path(root: Path = OUT) -> Path:
    return root / LEGACY_NAME


def _state_path(root: Path) -> Path:
    return brake_dir(root) / ".derived_state.json"


@contextmanager
def _locked(root: Path):
    brake_dir(root).mkdir(parents=True, exist_ok=True)
    handle = open(brake_dir(root) / ".lock", "a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


# ---------------------------------------------------------------------------
# holder set
# ---------------------------------------------------------------------------

def own_holders(root: Path = OUT):
    """Sorted list of (owner, record) for markers this protocol manages."""
    directory = brake_dir(root)
    if not directory.is_dir():
        return []
    found = []
    for path in sorted(directory.glob(PREFIX + "*")):
        owner = path.name[len(PREFIX):]
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            record = {"owner": owner, "note": "unparsable marker; treated as held"}
        found.append((owner, record))
    return found


def holders(root: Path = OUT):
    """Every holder, ours plus a foreign PAUSED_FOR_SIGNOFF_RERUN if present.

    The foreign entry is synthesised from the file, not stored: it exists exactly
    while the file does, so its placer releases it by deleting the file.
    """
    found = list(own_holders(root))
    if foreign_brake(root) is not None:
        path = derived_path(root)
        found.append((LEGACY_OWNER, {
            "owner": LEGACY_OWNER,
            "placed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z",
                                       time.localtime(path.stat().st_mtime)),
            "reason": ("a PAUSED_FOR_SIGNOFF_RERUN we did not write: another "
                       "party braked the run outside this protocol"),
            "release_when": ("its placer deletes the file; we neither own nor "
                             "rewrite it"),
            "tracked_not_owned": True,
            "text": path.read_text(encoding="utf-8", errors="replace"),
        }))
    return sorted(found, key=lambda item: item[0])


def _write_derived(root: Path, current):
    """Materialise the holder set into the file the deployed guard/lane read."""
    path = derived_path(root)
    owners = [owner for owner, _ in current]
    body = [
        SENTINEL,
        "Braked %s by the ownership-based brake protocol (_b9_brake.py)." % _now(),
        "",
        "Holders (%d) -- the run continues only when every one of them is gone:"
        % len(owners),
    ]
    for owner, record in current:
        body.append("  - %-18s placed %s: %s"
                    % (owner, record.get("placed_at", "?"),
                       record.get("reason", "(no reason recorded)")))
        if record.get("release_when"):
            body.append("      expected release: %s" % record["release_when"])
    body += [
        "",
        "This file is DERIVED.  Do not delete it to resume: it is rewritten from",
        "brakes/BRAKE_BY_* on every sync.  Release your own marker instead:",
        "  python /root/mk_v2/_b9_brake.py release <owner>",
        "Lanes stop after the unit in flight and the guard will not restart them",
        "while this file exists.",
        "",
    ]
    path.write_text("\n".join(body), encoding="utf-8")
    _state_path(root).write_text(json.dumps({
        "written_at": _now(),
        "owners": owners,
        "derived_mtime": path.stat().st_mtime,
    }, indent=2), encoding="utf-8")


def _derived_is_ours(root: Path) -> bool:
    """Did we write the derived file?

    Two independent witnesses, because each covers the other's blind spot:
    the sidecar (exact, but lost if our process dies between writes) and a
    sentinel first line inside the file itself (survives anything, and a
    foreign pause_b9.sh marker can never contain it).  Without the sentinel
    fallback, losing the sidecar would make our own brake look foreign, which
    would then need a human to clear -- a deadlock of our own making.
    """
    path = derived_path(root)
    if not path.is_file():
        return False
    try:
        if path.read_text(encoding="utf-8", errors="replace").startswith(SENTINEL):
            return True
    except OSError:
        return False
    state = _state_path(root)
    if not state.is_file():
        return False
    try:
        record = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return abs(path.stat().st_mtime - float(record.get("derived_mtime", -1))) < 1.0


def foreign_brake(root: Path = OUT):
    """The derived file if some other party wrote it, else None."""
    path = derived_path(root)
    if path.is_file() and not _derived_is_ours(root):
        return path
    return None


def _record_foreign(root: Path, path: Path):
    """Append-only observation log; never modifies the foreign file."""
    log = brake_dir(root) / "observed_foreign.jsonl"
    stamp = path.stat().st_mtime
    try:
        for line in log.read_text(encoding="utf-8").splitlines():
            if line.strip() and json.loads(line).get("file_mtime") == stamp:
                return
    except OSError:
        pass
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "observed_at": _now(),
            "file_mtime": stamp,
            "file_mtime_human": time.strftime("%Y-%m-%dT%H:%M:%S%z",
                                             time.localtime(stamp)),
            "text": path.read_text(encoding="utf-8", errors="replace"),
            "action": "tracked as holder unknown_legacy; file left untouched",
        }, ensure_ascii=False) + "\n")


def sync(root: Path = OUT):
    """Make the derived file agree with our holder set.  Returns the holders."""
    with _locked(root):
        foreign = foreign_brake(root)
        if foreign is not None:
            # somebody else's brake is already in force.  Writing our own text
            # over it would be a hijack, and it is unnecessary: the file already
            # stops the lanes.  Drop any stale ownership claim and record it.
            _record_foreign(root, foreign)
            _state_path(root).unlink(missing_ok=True)
            return holders(root), LEGACY_OWNER

        current = own_holders(root)
        path = derived_path(root)
        if current:
            state = _state_path(root)
            same = False
            if state.is_file() and _derived_is_ours(root):
                try:
                    same = (json.loads(state.read_text(encoding="utf-8"))
                            .get("owners") == [o for o, _ in current])
                except (OSError, ValueError):
                    same = False
            if not same:
                _write_derived(root, current)
        elif path.is_file():
            # only reachable after positively observing an empty holder set and
            # confirming the file is one we wrote ourselves
            archive = root / "archive"
            archive.mkdir(parents=True, exist_ok=True)
            os.replace(path, archive / ("%s.released_%s"
                                        % (LEGACY_NAME,
                                           time.strftime("%Y%m%dT%H%M%S"))))
            _state_path(root).unlink(missing_ok=True)
        return holders(root), None


def hold(owner: str, reason: str, release_when: str = "", root: Path = OUT):
    if not owner or "/" in owner:
        raise ValueError("owner must be a simple name")
    with _locked(root):
        marker = brake_dir(root) / (PREFIX + owner)
        existing = {}
        if marker.is_file():
            try:
                existing = json.loads(marker.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                existing = {}
        marker.write_text(json.dumps({
            "owner": owner,
            "placed_at": existing.get("placed_at", _now()),
            "refreshed_at": _now(),
            "pid": os.getpid(),
            "reason": reason,
            "release_when": release_when,
            "human_release_only": owner in HUMAN_RELEASE_ONLY,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
    return sync(root)


def release(owner: str, actor: str = "automation", root: Path = OUT):
    """Release one owner's marker.  Never touches any other owner's marker."""
    if owner == LEGACY_OWNER:
        return False, ("%r is tracked, not owned: it exists because another "
                       "party's %s is on disk.  Its placer releases it by "
                       "deleting that file; we must not."
                       % (LEGACY_OWNER, LEGACY_NAME))
    with _locked(root):
        marker = brake_dir(root) / (PREFIX + owner)
        if not marker.is_file():
            return False, "no marker for owner %r" % owner
        record = {}
        try:
            record = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        if (record.get("human_release_only") or owner in HUMAN_RELEASE_ONLY) \
                and actor != "human":
            return False, ("owner %r is human-release-only; rerun with "
                           "--actor human if you are one" % owner)
        archive = brake_dir(root) / "released"
        archive.mkdir(parents=True, exist_ok=True)
        os.replace(marker, archive / ("%s%s.released_%s"
                                      % (PREFIX, owner,
                                         time.strftime("%Y%m%dT%H%M%S"))))
    sync(root)
    return True, "released %r" % owner


# ---------------------------------------------------------------------------
# process helpers (no dependency on the retired chain trigger)
# ---------------------------------------------------------------------------

CRITICAL_NEEDLES = ("_mutant_worker.py", "run_e1_cse_falsify.py",
                    "_signoff_orch.py")


def _ppid(pid: int) -> int:
    try:
        for line in open("/proc/%d/status" % pid, encoding="utf-8"):
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except OSError:
        pass
    return 0


def find_processes(needle: str):
    """Processes whose cmdline contains ``needle``, minus self and ancestors.

    Never `pkill -f` / `pgrep -f`: the pattern matches the ssh command line that
    carries it, which has already both truncated a session and left the intended
    target alive.
    """
    excluded = set()
    pid = os.getpid()
    while pid and pid != 1:
        excluded.add(pid)
        pid = _ppid(pid)
    hits = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid in excluded:
            continue
        try:
            raw = Path("/proc/%d/cmdline" % pid).read_bytes()
        except OSError:
            continue
        cmdline = raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()
        if needle in cmdline:
            hits.append((pid, cmdline[:160]))
    return hits


def critical_path_processes():
    found = []
    for needle in CRITICAL_NEEDLES:
        for pid, cmdline in find_processes(needle):
            found.append((needle, pid, cmdline))
    return found


def gpu_compute_apps():
    try:
        smi = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory",
             "--format=csv,noheader"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return ["nvidia-smi unavailable: %s" % exc]
    return [line.strip() for line in smi.stdout.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _status(root: Path):
    current, foreign = sync(root)
    if foreign:
        print("a foreign %s is in force: tracked as holder %r, file untouched"
              % (LEGACY_NAME, foreign))
    print("brake directory : %s" % brake_dir(root))
    print("derived file    : %s (present=%s, written_by_us=%s)"
          % (derived_path(root), derived_path(root).is_file(),
             _derived_is_ours(root)))
    print("holders         : %d" % len(current))
    for owner, record in current:
        print("  - %-18s placed %s %s"
              % (owner, record.get("placed_at", "?"),
                 "(tracked, not owned)" if record.get("tracked_not_owned")
                 else "human_only=%s" % record.get("human_release_only", False)))
        print("      reason : %s" % record.get("reason", ""))
        if record.get("release_when"):
            print("      release: %s" % record["release_when"])
    print("effective state : %s"
          % ("BRAKED (lanes will not start)" if current
             else "CLEAR (lanes may start)"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "hold", "release", "sync"])
    parser.add_argument("owner", nargs="?")
    parser.add_argument("--reason", default="")
    parser.add_argument("--release-when", default="")
    parser.add_argument("--actor", default="automation")
    parser.add_argument("--root", type=Path, default=OUT)
    args = parser.parse_args()

    if args.action in ("status", "sync"):
        return _status(args.root)
    if not args.owner:
        parser.error("%s needs an owner" % args.action)
    if args.action == "hold":
        if not args.reason:
            parser.error("hold needs --reason: an unexplained brake is the "
                         "problem this protocol exists to fix")
        hold(args.owner, args.reason, args.release_when, args.root)
        print("held by %r" % args.owner)
        return _status(args.root)
    ok, message = release(args.owner, args.actor, args.root)
    print(message)
    _status(args.root)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
